from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .pricing import PriceBook, stable_template_id
from .emitter import JsonlEmitter
from .instrument import compute_cost  # reuse your function

from .providers.openai_adapter import OpenAIAdapter, OpenAIAdapterConfig
from .providers.vllm_adapter import VLLMAdapter, VLLMAdapterConfig
from .providers.gemini_adapter import GeminiAdapter, GeminiAdapterConfig


@dataclass(frozen=True)
class GatewayConfig:
    price_book_path: str
    events_jsonl_path: str
    region_default: str = "us"


class LLMGateway:
    def __init__(self, cfg: GatewayConfig):
        self.cfg = cfg
        self.price_book = PriceBook.load(cfg.price_book_path)
        self.emitter = JsonlEmitter(cfg.events_jsonl_path)

        # Lazy init adapters (only build if needed)
        self._openai: Optional[OpenAIAdapter] = None
        self._vllm: Optional[VLLMAdapter] = None
        self._gemini: Optional[GeminiAdapter] = None

    def _get_adapter(self, provider: str):
        provider = provider.lower()
        if provider == "openai":
            if not self._openai:
                api_key = os.environ["OPENAI_API_KEY"]
                self._openai = OpenAIAdapter(OpenAIAdapterConfig(api_key=api_key))
            return self._openai

        if provider == "vllm":
            if not self._vllm:
                base_url = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")
                api_key = os.environ.get("VLLM_API_KEY", "EMPTY")
                self._vllm = VLLMAdapter(VLLMAdapterConfig(base_url=base_url, api_key=api_key))
            return self._vllm

        if provider == "gemini":
            if not self._gemini:
                api_key = os.environ["GEMINI_API_KEY"]
                self._gemini = GeminiAdapter(GeminiAdapterConfig(api_key=api_key))
            return self._gemini

        raise ValueError(f"Unknown provider: {provider}")

    @staticmethod
    def _messages_to_prompt(messages: List[Dict[str, str]]) -> str:
        # For template hashing / chars; keep it deterministic.
        return "\n".join([f'{m.get("role","user")}: {m.get("content","")}' for m in messages])

    def chat(
        self,
        *,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        tenant_id: str,
        user_id: str,
        feature: str,
        endpoint: str,
        region: Optional[str] = None,
        request_id: Optional[str] = None,
        attempt: int = 1,
        retry_count: int = 0,
        cache_hit: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Returns: normalized adapter result + emits one usage event.
        """
        adapter = self._get_adapter(provider)
        region = region or self.cfg.region_default
        request_id = request_id or str(uuid.uuid4())

        ts = datetime.now(timezone.utc)
        t0 = time.perf_counter()

        status = "ok"
        result: Optional[Dict[str, Any]] = None

        prompt_for_hash = self._messages_to_prompt(messages)
        template_id = stable_template_id(prompt_for_hash)

        try:
            # Each adapter exposes .chat(model=..., messages=...)
            result = adapter.chat(model=model, messages=messages, **kwargs)
            return result
        except Exception:
            status = "error"
            raise
        finally:
            latency_ms = int((time.perf_counter() - t0) * 1000)

            pt = int((result or {}).get("prompt_tokens", 0) or 0)
            ct = int((result or {}).get("completion_tokens", 0) or 0)
            tt = int((result or {}).get("total_tokens", 0) or (pt + ct))

            # Price resolve (versioned) by timestamp
            price = self.price_book.resolve(provider, model, region, ts)

            unit_p = float(price.price_per_1k_prompt)
            unit_c = float(price.price_per_1k_completion)

            if cache_hit:
                cost = 0.0
            else:
                cost = float(compute_cost(pt, ct, unit_p, unit_c))

            event = {
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:23],  # ClickHouse-friendly DateTime64(3)
                "request_id": request_id,
                "attempt": int(attempt),

                "tenant_id": tenant_id,
                "user_id": user_id,
                "feature": feature,
                "endpoint": endpoint,
                "prompt_template_id": template_id,

                "provider": provider,
                "model": model,
                "region": region,

                "prompt_tokens": pt,
                "completion_tokens": ct,
                "total_tokens": tt,

                "latency_ms": int(latency_ms),
                "status": status,
                "retry_count": int(retry_count),
                "cache_hit": 1 if cache_hit else 0,

                "price_version": price.price_version,
                "unit_price_prompt": unit_p,
                "unit_price_completion": unit_c,
                "computed_cost": cost,

                "prompt_chars": len(prompt_for_hash),
                "completion_chars": 0,
            }
            self.emitter.emit(event)
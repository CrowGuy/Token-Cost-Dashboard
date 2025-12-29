from __future__ import annotations
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from .pricing import PriceBook, stable_template_id
from .emitter import JsonlEmitter

def compute_cost(prompt_tokens: int, completion_tokens: int, price_per_1k_prompt: float, price_per_1k_completion: float) -> float:
    return (prompt_tokens / 1000.0) * price_per_1k_prompt + (completion_tokens / 1000.0) * price_per_1k_completion

class LLMInstrumentor:
    def __init__(self, price_book: PriceBook, emitter: JsonlEmitter, provider_default: str = "openai", region_default: str = "us"):
        self.price_book = price_book
        self.emitter = emitter
        self.provider_default = provider_default
        self.region_default = region_default

    def call(
        self,
        fn: Callable[..., Any],
        *,
        tenant_id: str,
        user_id: str,
        feature: str,
        endpoint: str,
        prompt: str,
        model: str,
        provider: Optional[str] = None,
        region: Optional[str] = None,
        request_id: Optional[str] = None,
        attempt: int = 1,
        retry_count: int = 0,
        cache_hit: bool = False,
        # 你可以從 provider response 拿 tokens；這裡也允許你先手動丟進來做 demo
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        status_override: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        provider = provider or self.provider_default
        region = region or self.region_default
        request_id = request_id or str(uuid.uuid4())

        ts = datetime.now(timezone.utc)
        t0 = time.perf_counter()

        status = "ok"
        err: Optional[Exception] = None
        result: Any = None

        try:
            result = fn(prompt=prompt, model=model, **kwargs)
            return result
        except Exception as e:
            status = "error"
            err = e
            raise
        finally:
            latency_ms = int((time.perf_counter() - t0) * 1000)

            # tokens：優先用你傳入的；否則嘗試從 result 抽（不同 provider 格式不同，你之後再補）
            pt = int(prompt_tokens or 0)
            ct = int(completion_tokens or 0)
            total = pt + ct

            template_id = stable_template_id(prompt)

            # 價格（可回溯）：用 timestamp resolve 出當時的版本
            price = self.price_book.resolve(provider, model, region, ts)

            if cache_hit:
                unit_p = price.price_per_1k_prompt
                unit_c = price.price_per_1k_completion
                cost = 0.0
            else:
                unit_p = price.price_per_1k_prompt
                unit_c = price.price_per_1k_completion
                cost = compute_cost(pt, ct, unit_p, unit_c)

            event = {
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:23],
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
                "total_tokens": total,

                "latency_ms": latency_ms,
                "status": status_override or status,
                "retry_count": int(retry_count),
                "cache_hit": 1 if cache_hit else 0,

                "price_version": price.price_version,
                "unit_price_prompt": float(unit_p),
                "unit_price_completion": float(unit_c),
                "computed_cost": float(cost),

                "prompt_chars": len(prompt),
                "completion_chars": 0,
            }
            self.emitter.emit(event)
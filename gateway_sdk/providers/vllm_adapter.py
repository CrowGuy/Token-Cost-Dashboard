from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .openai_adapter import OpenAIAdapter, OpenAIAdapterConfig


@dataclass(frozen=True)
class VLLMAdapterConfig:
    base_url: str               # e.g. http://localhost:8000/v1
    api_key: str = "EMPTY"      # vLLM can be started with an api-key; many setups use a dummy token. :contentReference[oaicite:5]{index=5}


class VLLMAdapter:
    """
    vLLM OpenAI-compatible server adapter. :contentReference[oaicite:6]{index=6}
    Internally reuses OpenAIAdapter with base_url.
    """

    def __init__(self, cfg: VLLMAdapterConfig):
        self.cfg = cfg
        self._openai = OpenAIAdapter(OpenAIAdapterConfig(api_key=cfg.api_key, base_url=cfg.base_url))

    def chat(self, *, model: str, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        return self._openai.chat(model=model, messages=messages, **kwargs)
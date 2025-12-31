from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI


@dataclass(frozen=True)
class OpenAIAdapterConfig:
    api_key: str
    base_url: Optional[str] = None  # None -> official endpoint


class OpenAIAdapter:
    """
    OpenAI Chat Completions adapter.
    Uses the official openai-python SDK. :contentReference[oaicite:2]{index=2}
    """

    def __init__(self, cfg: OpenAIAdapterConfig):
        self.cfg = cfg
        if cfg.base_url:
            self.client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        else:
            self.client = OpenAI(api_key=cfg.api_key)

    def chat(self, *, model: str, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        """
        Returns normalized result:
        {
          "text": str,
          "prompt_tokens": int,
          "completion_tokens": int,
          "total_tokens": int,
          "raw": Any
        }
        """
        resp = self.client.chat.completions.create(model=model, messages=messages, **kwargs)
        text = (resp.choices[0].message.content or "") if resp.choices else ""

        # usage fields are commonly present on chat completion responses. :contentReference[oaicite:3]{index=3}
        usage = getattr(resp, "usage", None)
        pt = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
        ct = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
        tt = int(getattr(usage, "total_tokens", 0) or (pt + ct)) if usage else (pt + ct)

        return {
            "text": text,
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": tt,
            "raw": resp,
        }
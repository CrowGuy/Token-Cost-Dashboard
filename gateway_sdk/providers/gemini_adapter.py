from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from google import genai


@dataclass(frozen=True)
class GeminiAdapterConfig:
    api_key: str


class GeminiAdapter:
    """
    Gemini adapter using google-genai Client. :contentReference[oaicite:9]{index=9}
    We normalize output into the same structure as OpenAI/vLLM.
    """

    def __init__(self, cfg: GeminiAdapterConfig):
        self.cfg = cfg
        self.client = genai.Client(api_key=cfg.api_key)

    @staticmethod
    def _messages_to_text(messages: List[Dict[str, str]]) -> str:
        # MVP: simple join; later you can map roles to Gemini "parts"
        # This is good enough for producing real usage data and text responses.
        chunks = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            chunks.append(f"{role}: {content}")
        return "\n".join(chunks)

    def chat(self, *, model: str, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        prompt_text = self._messages_to_text(messages)

        # google-genai example pattern: client.models.generate_content(...) :contentReference[oaicite:10]{index=10}
        resp = self.client.models.generate_content(
            model=model,
            contents=prompt_text,
            **kwargs,
        )

        # Extract text (SDK response shape can evolve; keep it defensive)
        text = ""
        if hasattr(resp, "text") and resp.text:
            text = resp.text
        else:
            # fall back: try candidates
            candidates = getattr(resp, "candidates", None) or []
            if candidates:
                # try common nested fields
                content = getattr(candidates[0], "content", None)
                if content and getattr(content, "parts", None):
                    parts = content.parts
                    if parts and getattr(parts[0], "text", None):
                        text = parts[0].text

        # Token usage: depends on SDK/model; keep best-effort.
        # If you can't find usage, keep 0 and iterate later.
        pt = ct = tt = 0
        usage = getattr(resp, "usage_metadata", None) or getattr(resp, "usage", None)
        if usage:
            pt = int(getattr(usage, "prompt_token_count", 0) or getattr(usage, "prompt_tokens", 0) or 0)
            ct = int(getattr(usage, "candidates_token_count", 0) or getattr(usage, "completion_tokens", 0) or 0)
            tt = int(getattr(usage, "total_token_count", 0) or getattr(usage, "total_tokens", 0) or (pt + ct))

        return {
            "text": text,
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": tt,
            "raw": resp,
        }
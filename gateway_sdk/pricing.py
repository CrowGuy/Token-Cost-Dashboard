from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import yaml
import hashlib

@dataclass(frozen=True)
class Price:
    provider: str
    model: str
    region: str
    effective_from: datetime
    price_per_1k_prompt: float
    price_per_1k_completion: float
    price_version: str

def _parse_dt(s: str) -> datetime:
    # expects ISO8601 with Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)

class PriceBook:
    def __init__(self, prices: List[Price]):
        self.prices = prices

    @staticmethod
    def load(path: str) -> "PriceBook":
        raw = yaml.safe_load(open(path, "r", encoding="utf-8"))
        version = str(raw.get("version", "unknown"))
        prices: List[Price] = []
        for p in raw["prices"]:
            prices.append(
                Price(
                    provider=p["provider"],
                    model=p["model"],
                    region=p.get("region", "global"),
                    effective_from=_parse_dt(p["effective_from"]),
                    price_per_1k_prompt=float(p["price_per_1k_prompt"]),
                    price_per_1k_completion=float(p["price_per_1k_completion"]),
                    price_version=version,
                )
            )
        return PriceBook(prices)

    def resolve(self, provider: str, model: str, region: str, ts: datetime) -> Price:
        ts = ts.astimezone(timezone.utc)
        candidates = [
            p for p in self.prices
            if p.provider == provider and p.model == model and p.region == region and p.effective_from <= ts
        ]
        if not candidates:
            raise KeyError(f"No price for provider={provider}, model={model}, region={region}, ts={ts.isoformat()}")
        # pick latest effective_from
        return sorted(candidates, key=lambda x: x.effective_from)[-1]

def stable_template_id(prompt: str) -> str:
    # 不存原文，存 hash 當 template_id（你也可以改成你自己的 template key）
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
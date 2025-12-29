from __future__ import annotations
import json
import os
from typing import Dict, Any
from threading import Lock

class JsonlEmitter:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._lock = Lock()

    def emit(self, event: Dict[str, Any]) -> None:
        line = json.dumps(event, ensure_ascii=False)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
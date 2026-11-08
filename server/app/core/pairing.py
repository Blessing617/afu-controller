"""进程内共享状态（配对状态、当前任务等）。"""

from __future__ import annotations

import threading
import time
from datetime import datetime


class State:
    def __init__(self) -> None:
        self._started = time.monotonic()
        self._lock = threading.Lock()
        self.paired = False
        self.pairing_code: str | None = None
        self.pairing_code_expires_at: float = 0.0
        self.current_task: dict | None = None

    def uptime_seconds(self) -> int:
        return int(time.monotonic() - self._started)

    def now_iso(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    # ---- 配对码 ----
    def issue_pairing_code(self, ttl_seconds: int) -> str:
        import random

        code = f"{random.randint(0, 999999):06d}"
        with self._lock:
            self.pairing_code = code
            self.pairing_code_expires_at = time.monotonic() + ttl_seconds
        return code

    def check_pairing_code(self, code: str) -> bool:
        with self._lock:
            if not self.pairing_code:
                return False
            if time.monotonic() > self.pairing_code_expires_at:
                self.pairing_code = None
                return False
            ok = code.strip() == self.pairing_code
            if ok:
                # 一次性：用掉即失效
                self.pairing_code = None
            return ok


STATE = State()

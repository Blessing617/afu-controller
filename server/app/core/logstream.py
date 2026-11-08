"""引擎日志的增量读取、反刷屏与尾部缓冲。

为什么要有这一层
----------------
三个引擎的进度只能从日志里读（原神没有对外接口；星铁虽然有运行记录，日志仍然是最
细的信息源）。但日志有两个坑：

1. **不能整读**。MAA 的 `asst.log` 一天能到 8MB，星铁锄大地能跑几小时；整读会让内存
   随任务时长线性增长。
2. **不能把"有日志"当"有进展"**。引擎卡住时常常每秒刷同一行错误
   （2026-11-07 23:44 那次星铁就是每秒刷「截图失败：没有找到游戏窗口」），
   若不折叠重复行，进展计时永远刷新，卡死检测形同虚设。

所以这里做三件事：按字节偏移增量读、按行切分（不切断多字节字符）、连续重复行折叠。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

# 尾部保留多少行给手机端看。50 行已经够判断"卡在哪一步"，再多只是浪费内存。
KEEP_LINES = 200
# 同一行连续出现超过这个次数就开始折叠
REPEAT_LIMIT = 3


class LogStream:
    """跟踪一个日志文件的增量内容。

    一个实例绑定一次运行：构造时确定起点偏移，之后只读它之后的新内容。
    这样「上一次运行的成功标志」不会污染这一次。
    """

    def __init__(
        self,
        path: str | Path,
        *,
        keep: int = KEEP_LINES,
        repeat_limit: int = REPEAT_LIMIT,
        from_start: bool = False,
    ) -> None:
        self.path = Path(path)
        self.keep = max(1, keep)
        self.repeat_limit = max(1, repeat_limit)
        self._lock = threading.Lock()
        self._offset = 0 if from_start else self._current_size()
        self._tail: list[str] = []
        self._last_raw = ""
        self._repeat = 0
        self._progressed = False
        self._last_progress_at = time.monotonic()

    # ---------------- 内部 ----------------
    def _current_size(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0

    def _append(self, line: str) -> None:
        self._tail.append(line)
        overflow = len(self._tail) - self.keep
        if overflow > 0:
            del self._tail[:overflow]

    def _replace_last(self, line: str) -> None:
        if self._tail:
            self._tail[-1] = line
        else:
            self._append(line)

    # ---------------- 对外 ----------------
    def read_new(self) -> list[str]:
        """读取自上次调用以来的新行（已折叠重复），返回新增的行。"""
        with self._lock:
            self._progressed = False
            if not self.path.is_file():
                return []

            size = self._current_size()
            if size < self._offset:
                # 文件被清空或轮转：从头开始，且不要把旧内容当成本次进展
                self._offset = 0
                self._last_raw = ""
                self._repeat = 0
            if size == self._offset:
                return []

            try:
                with self.path.open("rb") as fh:
                    fh.seek(self._offset)
                    data = fh.read()
            except OSError:
                return []

            # 只消费到最后一个换行为止：半行留到下次，避免把多字节字符切成乱码
            last_nl = data.rfind(b"\n")
            if last_nl < 0:
                return []
            chunk = data[: last_nl + 1]
            self._offset += len(chunk)
            text = chunk.decode("utf-8", errors="replace")

            added: list[str] = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line == self._last_raw:
                    self._repeat += 1
                    if self._repeat <= self.repeat_limit:
                        # 阈值内的重复仍然记录下来（用户要看得见是同一句在刷）
                        self._append(line)
                        added.append(line)
                    else:
                        # 超过阈值：不再追加，只把最后一条改写为计数说明
                        self._replace_last(f"{line}（已重复 {self._repeat} 次）")
                    continue
                self._last_raw = line
                self._repeat = 1
                self._append(line)
                added.append(line)
                self._progressed = True

            if self._progressed:
                self._last_progress_at = time.monotonic()
            return added

    # ---------------- 状态 ----------------
    @property
    def tail(self) -> list[str]:
        with self._lock:
            return list(self._tail)

    @property
    def progressed(self) -> bool:
        """最近一次 read_new 是否带来了有效新进展。"""
        with self._lock:
            return self._progressed

    @property
    def last_progress_at(self) -> float:
        with self._lock:
            return self._last_progress_at

    def touch(self) -> None:
        """外部证据也算进展（例如运行记录出现、心跳显示仍在跑）。"""
        with self._lock:
            self._last_progress_at = time.monotonic()
            self._progressed = True

    def idle_seconds(self) -> float:
        return time.monotonic() - self.last_progress_at

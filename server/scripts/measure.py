"""性能测量：给「内存 / CPU / 截图」三个预算提供可复现的数字。

用法（在 server 目录下）：

    .venv\\Scripts\\python.exe scripts/measure.py            # 跑一遍并打印
    .venv\\Scripts\\python.exe scripts/measure.py --shots 50 # 多测几张截图

测什么：

| 指标 | 口径 |
|---|---|
| 电脑端工作集 | 正在运行的 `阿福代肝控制器.exe` 的 WorkingSet64（没有就跳过） |
| 空闲 CPU | 该进程在一段时间内的 CPU 时间增量 / 墙钟时间 |
| 截图耗时与体积 | 直接调用 `capture()`，取中位数与最大值 |
| 截图链路内存 | 连续截图前后的本进程工作集差值 |

这些数字对应 `.spec/specs/performance` 的预算，改代码前后各跑一次即可对比。
"""

from __future__ import annotations

import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MB = 1024 * 1024
APP_NAME = "阿福代肝控制器.exe"


def _powershell(script: str, timeout: float = 20) -> str:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=timeout,
            creationflags=0x08000000,
        )
        return out.stdout.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def app_working_set() -> int | None:
    """正在运行的桌面端进程工作集（字节）。没运行就返回 None。"""
    text = _powershell(
        f"Get-Process -Name '{APP_NAME[:-4]}' -ErrorAction SilentlyContinue | "
        "Measure-Object -Property WorkingSet64 -Sum | Select-Object -ExpandProperty Sum"
    )
    try:
        value = int(text.splitlines()[-1])
        return value or None
    except Exception:
        return None


def app_cpu_seconds() -> float | None:
    text = _powershell(
        f"Get-Process -Name '{APP_NAME[:-4]}' -ErrorAction SilentlyContinue | "
        "Measure-Object -Property CPU -Sum | Select-Object -ExpandProperty Sum"
    )
    try:
        return float(text.splitlines()[-1])
    except Exception:
        return None


def measure_idle_cpu(seconds: float = 10.0) -> float | None:
    """空闲 CPU 占用（单核百分比）。"""
    before = app_cpu_seconds()
    if before is None:
        return None
    time.sleep(seconds)
    after = app_cpu_seconds()
    if after is None:
        return None
    return max(0.0, (after - before) / seconds * 100.0)


def measure_capture(shots: int) -> list[dict]:
    from app.platform.capture import capture

    rows = []
    for _ in range(shots):
        try:
            r = capture("genshin")
        except Exception as exc:  # noqa: BLE001 —— 黑屏/独占全屏时会抛，记录下来继续
            rows.append({"error": str(exc)})
            continue
        rows.append({"ms": r.elapsed_ms, "kb": len(r.data) / 1024, "w": r.width, "h": r.height})
    return rows


def main(argv: list[str]) -> int:
    shots = 20
    if "--shots" in argv:
        shots = int(argv[argv.index("--shots") + 1])

    print("=" * 56)
    print("电脑端常驻资源")
    ws = app_working_set()
    if ws is None:
        print(f"  {APP_NAME} 没在运行，跳过（先启动桌面端再测）")
    else:
        print(f"  工作集      {ws / MB:7.1f} MB   （预算 ≤ 120 MB）")
        cpu = measure_idle_cpu(10)
        if cpu is not None:
            print(f"  空闲 CPU    {cpu:7.2f} %/核 （预算 ≤ 1 %）")

    print("=" * 56)
    print(f"截图链路（{shots} 张）")
    rows = measure_capture(shots)
    ok = [r for r in rows if "ms" in r]
    if not ok:
        print("  全部失败：", rows[0].get("error") if rows else "无结果")
    else:
        times = [r["ms"] for r in ok]
        sizes = [r["kb"] for r in ok]
        print(f"  耗时中位 {statistics.median(times):6.1f} ms   最大 {max(times):6.1f} ms （预算 < 200 ms）")
        print(f"  体积中位 {statistics.median(sizes):6.1f} KB   最大 {max(sizes):6.1f} KB （预算 < 300 KB）")
        print(f"  输出尺寸 {ok[0]['w']}×{ok[0]['h']}（预算宽度 ≤ 960）")

    if ws is not None:
        after = app_working_set()
        if after:
            print(f"  连续截图后工作集 {after / MB:.1f} MB（差值 {(after - ws) / MB:+.1f} MB，预算 ≤ +20 MB）")

    print("=" * 56)
    print("手机端：真机执行 `adb shell dumpsys meminfo com.afu.controller` 看 TOTAL PSS（预算 ≤ 200 MB）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

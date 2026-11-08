"""日志增量读取与反刷屏的测试。"""

from __future__ import annotations

from pathlib import Path

from app.core.logstream import LogStream


def _write(path: Path, text: str, append: bool = True) -> None:
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def test_from_now_ignores_previous_run(tmp_path: Path):
    """上一次运行留下的内容不能被当成本次的进展。"""
    log = tmp_path / "run.log"
    _write(log, "上一次运行：一条龙和配置组任务结束\n", append=False)

    stream = LogStream(log)
    assert stream.read_new() == []

    _write(log, "本次：任务启动！\n")
    assert stream.read_new() == ["本次：任务启动！"]
    assert not any("上一次运行" in line for line in stream.tail)


def test_repeated_line_is_collapsed(tmp_path: Path):
    """同一行刷 1 万次，不能把缓冲刷爆。"""
    log = tmp_path / "run.log"
    log.write_text("", encoding="utf-8")

    stream = LogStream(log, repeat_limit=3)
    _write(log, "截图失败：没有找到游戏窗口\n" * 10_000)
    added = stream.read_new()

    # 前几次算新增，之后被折叠
    assert len(added) == 3
    assert stream.progressed is True

    # 再刷同样的内容：不算进展
    _write(log, "截图失败：没有找到游戏窗口\n" * 1000)
    stream.read_new()
    assert stream.progressed is False

    same = [line for line in stream.tail if line.startswith("截图失败")]
    assert len(same) <= 3, f"重复行没被折叠：{len(same)} 条"
    assert "已重复" in same[-1]


def test_tail_is_bounded(tmp_path: Path):
    """长跑时尾部缓冲有上界。"""
    log = tmp_path / "run.log"
    log.write_text("", encoding="utf-8")
    stream = LogStream(log, keep=50)

    for i in range(500):
        _write(log, f"第 {i} 行，内容各不相同\n")
    stream.read_new()

    assert len(stream.tail) == 50
    assert stream.tail[-1].startswith("第 499 行")


def test_half_line_is_not_consumed(tmp_path: Path):
    """写到一半的行要留到下次，不能把多字节字符切坏。"""
    log = tmp_path / "run.log"
    log.write_text("", encoding="utf-8")
    stream = LogStream(log)

    _write(log, "完整的行\n写到一半的中")
    assert stream.read_new() == ["完整的行"]

    _write(log, "文行\n")
    assert stream.read_new() == ["写到一半的中文行"]


def test_missing_file_is_not_an_error(tmp_path: Path):
    stream = LogStream(tmp_path / "还没生成.log")
    assert stream.read_new() == []
    assert stream.tail == []


def test_truncated_file_restarts(tmp_path: Path):
    """日志被清空/轮转后不能因为偏移过大而卡死。"""
    log = tmp_path / "run.log"
    _write(log, "旧内容旧内容旧内容\n" * 3, append=False)
    stream = LogStream(log, from_start=True)
    stream.read_new()

    log.write_text("新\n", encoding="utf-8")
    assert stream.read_new() == ["新"]

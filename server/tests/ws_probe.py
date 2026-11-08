"""订阅 /ws，验证任务事件流。"""
import asyncio, json, sys, io, time

import websockets


async def main(token: str, seconds: int = 90) -> None:
    uri = f"ws://127.0.0.1:8765/ws?token={token}"
    events = []
    try:
        async with websockets.connect(uri) as ws:
            print("已连接 WS", flush=True)
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic())
                except asyncio.TimeoutError:
                    break
                data = json.loads(msg)
                kind = data.get("type")
                if kind == "task":
                    ev = data.get("event")
                    task = data.get("task") or {}
                    print(f"  事件: {ev} -> {task.get('title')} {task.get('state')}", flush=True)
                    events.append(ev)
                else:
                    print(f"  {kind}", flush=True)
    except Exception as exc:
        print(f"WS 失败: {exc}", flush=True)

    ok = "started" in events and "finished" in events
    print(f"结果: 收到 {events} -> {'✅ 通过' if ok else '⚠ 只收到部分'}", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    token = sys.argv[1]
    asyncio.run(main(token))

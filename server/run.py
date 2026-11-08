"""启动脚本：读取配置里的 host/port 后运行服务。

用法（在 server 目录下）：
    .venv\\Scripts\\python.exe run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn

from app.core.config import load_config, resolve_port


def main() -> None:
    cfg = load_config()
    host = cfg.get("host", "0.0.0.0")
    # 端口自适应：首选端口被占时自动换一个，并把实际端口写回配置
    port = resolve_port()
    print(f"[game-orchestrator] listening on http://{host}:{port}", flush=True)
    uvicorn.run(
        "app.main:app", host=host, port=port, log_level="info", access_log=False
    )


if __name__ == "__main__":
    main()

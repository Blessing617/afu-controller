"""FastAPI 应用入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .platform import keepawake
from .api import (
    chain, debug, deps, games, health, maa, net, onboarding, pair, schedule, screen, status, tasks,
)
from .core.auth import auth_middleware, ensure_pairing_code
from .core.config import DATA_DIR as SERVER_DATA
from .core.config import load_config
from .core.state import add_listener
from .api.ws import emit_chain_event, emit_task_event, router as ws_router

VERSION = "0.1.0"

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _swagger_static_dirs() -> list[tuple[str, str]]:
    """swagger-ui 的本地静态资源。

    为什么不用 FastAPI 默认的 /docs：它把 css/js 指向 cdn.jsdelivr.net，
    国内网络下实测 5 秒才响应，浏览器直接白屏（用户以为「网页打不开」）。
    装上 swagger-ui-bundle 后资源就在本地，断网也能看文档。

    注意：不能直接用 `swagger_ui_bundle.swagger_ui_path`——打包后目录名
    被我们改成了 `swagger-ui`，而包属性里仍写着 `swagger-ui-4.15.5`，
    照抄就会 404。所以这里解析包的实际位置后逐个目录找。
    """
    try:
        import swagger_ui_bundle  # type: ignore

        base = Path(swagger_ui_bundle.__file__).resolve().parent
    except Exception:  # noqa: BLE001
        return []

    candidates = [
        base / "vendor" / "swagger-ui",          # 打包后的目录名
        base / "vendor" / "swagger-ui-4.15.5",   # 源码安装的默认目录名
    ]
    # 兜底：vendor 下任意 swagger-ui 开头的目录（版本升级也不会失效）
    vendor = base / "vendor"
    if vendor.is_dir():
        candidates += sorted(
            p for p in vendor.iterdir() if p.is_dir() and p.name.startswith("swagger-ui")
        )

    seen: set[str] = set()
    for path in candidates:
        try:
            key = str(path.resolve()).lower()
        except OSError:
            key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        # 认这个目录的标志是有 css 和 bundle
        if (path / "swagger-ui.css").is_file() and (path / "swagger-ui-bundle.js").is_file():
            return [("/swagger-assets", str(path))]
    return []


@asynccontextmanager
async def lifespan(app: FastAPI):
    add_listener(emit_task_event)
    from .core.orchestrator import add_listener as add_chain_listener

    add_chain_listener(emit_chain_event)
    cfg = load_config()

    # 服务重启后内存里的配对码已失效；文件若还在会误导用户，这里清掉。
    # （内存里有码时会重新写文件，所以不会误删有效的码）
    from .core.pairing import STATE as _S

    if _S.pairing_code is None:
        hint = SERVER_DATA / "pairing_code.txt"
        try:
            hint.unlink(missing_ok=True)
        except Exception:
            pass

    ensure_pairing_code(int(cfg.get("pairing_code_ttl_seconds", 300)))

    # 服务常驻期间保持电脑唤醒：不然用户带手机出门，电脑一自动锁屏就什么都干不了
    from .core.state import RUNNER as _RUNNER

    keepawake.set_busy_probe(lambda: _RUNNER.current() is not None)
    keepawake.start()

    # 定时执行：到点先重置环境，再从头跑整条链
    from .core.scheduler import SCHEDULER as _SCHEDULER

    _SCHEDULER.start()
    try:
        yield
    finally:
        _SCHEDULER.stop()
        keepawake.stop()


app = FastAPI(
    title="Game Orchestrator",
    version=VERSION,
    lifespan=lifespan,
    # 关闭自带文档，下面用本地资源重新注册
    docs_url=None,
    redoc_url=None,
)
app.middleware("http")(auth_middleware)
app.include_router(health.router)
app.include_router(pair.router)
app.include_router(status.router)
app.include_router(net.router)
app.include_router(onboarding.router)
app.include_router(deps.router)
app.include_router(games.router)
app.include_router(tasks.router)
app.include_router(chain.router)
app.include_router(schedule.router)
app.include_router(maa.router)
app.include_router(screen.router)
app.include_router(debug.router)
app.include_router(ws_router)


# ---------------- 静态资源 ----------------
_SWAGGER_DIRS = _swagger_static_dirs()
for mount_path, directory in _SWAGGER_DIRS:
    app.mount(mount_path, StaticFiles(directory=directory), name="swagger-assets")

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 有本地资源就用本地的；没有就退回默认（会走 CDN，但至少页面不崩）
_LOCAL_SWAGGER = bool(_SWAGGER_DIRS)


@app.get("/docs", include_in_schema=False)
def api_docs():
    """接口文档。

    资源指向本地 /swagger-assets，断网也能打开。
    以前用默认实现，css/js 都走 cdn.jsdelivr.net，实测 5 秒才响应，浏览器白屏。
    """
    from fastapi.openapi.docs import get_swagger_ui_html

    if _LOCAL_SWAGGER:
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{app.title} · 接口文档",
            swagger_js_url="/swagger-assets/swagger-ui-bundle.js",
            swagger_css_url="/swagger-assets/swagger-ui.css",
            swagger_favicon_url="/swagger-assets/favicon-32x32.png",
        )
    return get_swagger_ui_html(
        openapi_url="/openapi.json", title=f"{app.title} · 接口文档"
    )


@app.get("/welcome", include_in_schema=False)
def welcome() -> FileResponse:
    """首次引导页。桌面应用在第一次运行时会打开它。"""
    page = STATIC_DIR / "welcome.html"
    if not page.is_file():
        from fastapi.responses import RedirectResponse

        return RedirectResponse("/")
    return FileResponse(page, media_type="text/html; charset=utf-8")


@app.get("/", include_in_schema=False)
def console() -> FileResponse:
    """内置网页控制台。离线可渲染，不依赖外部 CDN。"""
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        from fastapi.responses import HTMLResponse

        return HTMLResponse(
            "<h1>阿福代肝控制器</h1><p>控制台页面缺失，请重新安装或检查 static/index.html。</p>"
        )
    return FileResponse(index, media_type="text/html; charset=utf-8")

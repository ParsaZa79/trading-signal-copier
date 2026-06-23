"""FastAPI main application."""

import asyncio
import importlib.util
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Load executor module directly to avoid importing telethon from bot's __init__.py
bot_src_path = Path(__file__).parent.parent.parent / "bot" / "src"

# Load the executor module directly without triggering package __init__.py
def _load_module_directly(module_name: str, file_path: Path):
    """Load a module directly from file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# First load dependencies that executor needs
_load_module_directly(
    "tania_signal_copier.models",
    bot_src_path / "tania_signal_copier" / "models.py"
)
_load_module_directly(
    "tania_signal_copier.mt5_adapter",
    bot_src_path / "tania_signal_copier" / "mt5_adapter.py"
)
executor_module = _load_module_directly(
    "tania_signal_copier.executor",
    bot_src_path / "tania_signal_copier" / "executor.py"
)
MT5Executor = executor_module.MT5Executor

from .config import config
from .account_store import ensure_default_account, get_websocket_account
from .dependencies import clear_mt5_executor, get_executor_for_account_id, set_mt5_executor_factory
from .routers import (
    account,
    accounts,
    analysis,
    auth,
    bot,
    health,
    mt5,
    orders,
    positions,
    prompts,
    symbols,
    telegram,
)
from .routers import (
    config as config_router,
)
from .routers.bot import set_log_manager
from .security import bootstrap_admin_from_env, current_user_for_websocket, get_current_user
from .services.history_service import init_database
from .websocket.broadcaster import start_broadcaster
from .websocket.log_manager import log_manager
from .websocket.manager import manager

# Background task reference
_broadcaster_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    global _broadcaster_task

    print("Starting Trading Dashboard API...")

    # Set up log manager for bot router
    set_log_manager(log_manager)

    # Initialize database
    await init_database()

    set_mt5_executor_factory(MT5Executor)
    admin = bootstrap_admin_from_env()
    if admin:
        ensure_default_account(admin)

    # Start account-aware WebSocket broadcaster.
    _broadcaster_task = asyncio.create_task(
        start_broadcaster(get_executor_for_account_id, manager)
    )

    yield

    # Shutdown
    print("Shutting down...")

    # Cancel broadcaster
    if _broadcaster_task:
        _broadcaster_task.cancel()
        try:
            await _broadcaster_task
        except asyncio.CancelledError:
            pass

    clear_mt5_executor()

    print("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Trading Dashboard API",
    description="API for managing MT5 trading positions and orders",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
protected = [Depends(get_current_user)]
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Accounts"], dependencies=protected)
app.include_router(health.router, prefix="/api/health", tags=["Health"], dependencies=protected)
app.include_router(mt5.router, prefix="/api/mt5", tags=["MT5"], dependencies=protected)
app.include_router(positions.router, prefix="/api/positions", tags=["Positions"], dependencies=protected)
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"], dependencies=protected)
app.include_router(account.router, prefix="/api/account", tags=["Account"], dependencies=protected)
app.include_router(symbols.router, prefix="/api/symbols", tags=["Symbols"], dependencies=protected)
app.include_router(telegram.router, prefix="/api/telegram", tags=["Telegram"], dependencies=protected)
app.include_router(bot.router, prefix="/api/bot", tags=["Bot"], dependencies=protected)
app.include_router(config_router.router, prefix="/api/config", tags=["Config"], dependencies=protected)
app.include_router(prompts.router, prefix="/api/prompts", tags=["Prompts"], dependencies=protected)
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"], dependencies=protected)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Trading Dashboard API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates.

    Clients connect here to receive position and account updates.
    """
    user = current_user_for_websocket(websocket)
    account = get_websocket_account(user, websocket.query_params.get("account_id")) if user else None
    if not user or not account:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, account["id"])
    try:
        while True:
            # Keep connection alive, handle any client messages
            data = await websocket.receive_text()
            # Could handle subscription requests or pings here
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.websocket("/ws/logs")
async def logs_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming bot logs.

    Clients connect here to receive real-time bot output.
    """
    user = current_user_for_websocket(websocket)
    account = get_websocket_account(user, websocket.query_params.get("account_id")) if user else None
    if not user or not account:
        await websocket.close(code=1008)
        return

    connected = await log_manager.connect(websocket, account["id"])
    if not connected:
        return

    try:
        while True:
            # Keep connection alive, handle any client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            elif data == "clear":
                log_manager.clear_buffer(account["id"])
    except WebSocketDisconnect:
        log_manager.disconnect(websocket)
    except Exception as e:
        print(f"Log WebSocket error: {e}")
        log_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.debug,
    )

"""Session Baton — structured cross-session state handoff for AI coding agents.

Part of the ACA (Agent Civilization Architecture) ecosystem.
Implements ACA Layer 1 Memory session-state extension.
"""

from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.models import (
    BatonReadRequest,
    BatonReadResponse,
    BatonWriteRequest,
    BatonWriteResponse,
)
from src.storage import BatonStore

API_TOKEN = os.environ.get("BATON_API_TOKEN", "")
DB_PATH = Path(os.environ.get("BATON_DB_PATH", "data/baton.sqlite3"))
HOST = os.environ.get("BATON_HOST", "127.0.0.1")
PORT = int(os.environ.get("BATON_PORT", "9101"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = BatonStore(DB_PATH)
    try:
        yield
    finally:
        app.state.store.close()


app = FastAPI(
    title="session-baton",
    description="Structured cross-session state handoff for AI coding agents. ACA Layer 1 extension.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def require_api_token(request: Request, call_next):
    if request.scope["path"].rstrip("/") == "/health":
        return await call_next(request)
    if not API_TOKEN:
        return await call_next(request)
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "missing bearer token"})
    if not hmac.compare_digest(header[7:], API_TOKEN):
        return JSONResponse(status_code=401, content={"detail": "invalid token"})
    return await call_next(request)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "session-baton"}


@app.post("/v1/baton/read", response_model=BatonReadResponse)
async def read_baton(payload: BatonReadRequest, request: Request) -> BatonReadResponse:
    store: BatonStore = request.app.state.store
    baton, updated_at = store.read(payload.namespace)
    return BatonReadResponse(baton=baton, namespace=payload.namespace, updated_at=updated_at)


@app.post("/v1/baton/write", response_model=BatonWriteResponse)
async def write_baton(payload: BatonWriteRequest, request: Request) -> BatonWriteResponse:
    store: BatonStore = request.app.state.store
    updated_at = store.write(payload.namespace, payload.baton)
    return BatonWriteResponse(ok=True, updated_at=updated_at, namespace=payload.namespace)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.server:app", host=HOST, port=PORT, reload=True)

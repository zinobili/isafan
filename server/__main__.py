"""`python -m server` — run the app with uvicorn using values from config."""

from __future__ import annotations

import uvicorn

from .config import settings

if __name__ == "__main__":
    tls = {}
    if settings.ssl_certfile and settings.ssl_keyfile:
        tls = {"ssl_certfile": settings.ssl_certfile, "ssl_keyfile": settings.ssl_keyfile}
    uvicorn.run(
        "server.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        **tls,
    )

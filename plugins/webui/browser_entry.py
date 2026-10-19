"""Standalone browser entry for the WebUI without moving the ATRI host."""

import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

WEBUI_HOST = os.getenv("WEBUI_HOST", "127.0.0.1")
WEBUI_PORT = int(os.getenv("WEBUI_PORT", "8188"))
WEBUI_BROWSER_URL = f"http://{WEBUI_HOST}:{WEBUI_PORT}/webui"
WEBUI_UPSTREAM = os.getenv("WEBUI_UPSTREAM", "http://127.0.0.1:8080").rstrip("/")
STATIC_WEBUI_PATH = Path(__file__).parent / "static" / "webui"
HOP_BY_HOP_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

app = FastAPI(title="ATRI WebUI browser entry", docs_url=None, redoc_url=None)


@app.get("/health", include_in_schema=False)
async def health_check():
    try:
        async with httpx.AsyncClient(timeout=2, follow_redirects=False) as client:
            response = await client.get(f"{WEBUI_UPSTREAM}/")
    except httpx.HTTPError:
        return JSONResponse({"status": "unavailable"}, status_code=503)

    return {"status": "ok", "upstream_status": response.status_code}


@app.get("/", include_in_schema=False)
async def redirect_to_webui():
    return RedirectResponse(url="/webui/")


app.mount("/webui", StaticFiles(directory=STATIC_WEBUI_PATH, html=True), name="webui")


@app.api_route("/{path:path}", methods=["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"])
async def proxy_webui_api(path: str, request: Request):
    """Forward WebUI API calls to ATRI's shared internal host."""
    target = f"{WEBUI_UPSTREAM}/{path}"
    headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() not in HOP_BY_HOP_HEADERS
    }

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                target,
                params=request.query_params,
                content=await request.body(),
                headers=headers,
            )
    except httpx.HTTPError:
        return JSONResponse({"detail": "ATRI WebUI API is unavailable"}, status_code=503)

    response_headers = {
        name: value
        for name, value in upstream.headers.items()
        if name.lower() not in HOP_BY_HOP_HEADERS
    }
    return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=WEBUI_HOST, port=WEBUI_PORT)

"""FastAPI gateway router with reverse proxy to internal dev servers."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from sandbox.process_manager import ProcessManager

logger = logging.getLogger(__name__)

# Module name to internal port mapping
MODULE_PORTS = {
    "prototype": 3001,
    "frontend": 3002,
    "dbml": 3003,
    "tests": 3004,
}

# HTTP methods to proxy
PROXY_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]

# Headers that should not be forwarded
HOP_BY_HOP_HEADERS = frozenset(
    [
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    ]
)


def filter_headers(headers: dict) -> dict:
    """Remove hop-by-hop headers that shouldn't be forwarded."""
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP_HEADERS}


class GatewayRouter:
    """
    HTTP and WebSocket reverse proxy for routing to internal dev servers.

    Routes requests based on the module path segment:
    /connect/{user}/{project}/{module}/* → localhost:{MODULE_PORTS[module]}/*
    """

    def __init__(
        self,
        process_manager: "ProcessManager | None" = None,
        client_timeout: float = 30.0,
    ):
        """
        Initialize the gateway router.

        Args:
            process_manager: Optional ProcessManager for health checks.
            client_timeout: Timeout for proxied HTTP requests in seconds.
        """
        self.process_manager = process_manager
        self.client_timeout = client_timeout
        self._http_client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        """Initialize the HTTP client."""
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.client_timeout),
            follow_redirects=False,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )
        logger.info("Gateway HTTP client initialized")

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        logger.info("Gateway HTTP client closed")

    def _get_target_url(self, module: str, path: str, query_string: str) -> str:
        """Build the target URL for a proxy request."""
        port = MODULE_PORTS.get(module)
        if not port:
            raise HTTPException(status_code=404, detail=f"Unknown module: {module}")

        url = f"http://127.0.0.1:{port}/{path}"
        if query_string:
            url = f"{url}?{query_string}"
        return url

    async def proxy_http(
        self,
        request: Request,
        user: str,
        project: str,
        module: str,
        path: str,
    ) -> Response:
        """
        Proxy an HTTP request to an internal dev server.

        Args:
            request: The incoming FastAPI request.
            user: User identifier from URL.
            project: Project identifier from URL.
            module: Target module (prototype, frontend, dbml, tests).
            path: Path to forward to the internal server.

        Returns:
            Response from the internal server.

        Raises:
            HTTPException: If the module is unknown or server is unavailable.
        """
        if not self._http_client:
            raise HTTPException(status_code=503, detail="Gateway not initialized")

        target_url = self._get_target_url(module, path, str(request.query_params))

        # Build request headers
        headers = filter_headers(dict(request.headers))
        headers["host"] = f"127.0.0.1:{MODULE_PORTS[module]}"
        headers["x-forwarded-for"] = request.client.host if request.client else "unknown"
        headers["x-forwarded-proto"] = request.url.scheme
        headers["x-devlabo-user"] = user
        headers["x-devlabo-project"] = project

        # Get request body
        body = await request.body()

        try:
            response = await self._http_client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )

            # Filter response headers
            response_headers = filter_headers(dict(response.headers))

            # Stream large responses
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > 1024 * 1024:  # > 1MB
                return StreamingResponse(
                    response.aiter_bytes(),
                    status_code=response.status_code,
                    headers=response_headers,
                )

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
            )

        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to {module} server: {e}")
            raise HTTPException(
                status_code=502, detail=f"Cannot connect to {module} server"
            ) from e

        except httpx.TimeoutException as e:
            logger.error(f"Timeout connecting to {module} server: {e}")
            raise HTTPException(
                status_code=504, detail=f"Timeout connecting to {module} server"
            ) from e

        except httpx.HTTPError as e:
            logger.error(f"HTTP error proxying to {module}: {e}")
            raise HTTPException(status_code=502, detail=f"Error proxying to {module}") from e

    async def proxy_websocket(
        self,
        websocket: WebSocket,
        user: str,
        project: str,
        module: str,
        path: str,
    ) -> None:
        """
        Proxy a WebSocket connection to an internal dev server (for Vite HMR).

        Args:
            websocket: The incoming WebSocket connection.
            user: User identifier from URL.
            project: Project identifier from URL.
            module: Target module (prototype, frontend, dbml, tests).
            path: Path to forward to the internal server.
        """
        port = MODULE_PORTS.get(module)
        if not port:
            await websocket.close(code=4004, reason=f"Unknown module: {module}")
            return

        # Accept the client connection first
        await websocket.accept()

        # Build WebSocket URL for internal server
        query_string = str(websocket.query_params)
        ws_url = f"ws://127.0.0.1:{port}/{path}"
        if query_string:
            ws_url = f"{ws_url}?{query_string}"

        logger.debug(f"Proxying WebSocket to {ws_url}")

        try:
            # Connect to internal WebSocket
            import websockets

            async with websockets.connect(ws_url) as internal_ws:
                # Create bidirectional forwarding tasks
                async def forward_to_internal() -> None:
                    try:
                        while True:
                            data = await websocket.receive()
                            if "text" in data:
                                await internal_ws.send(data["text"])
                            elif "bytes" in data:
                                await internal_ws.send(data["bytes"])
                    except WebSocketDisconnect:
                        pass

                async def forward_to_client() -> None:
                    try:
                        async for message in internal_ws:
                            if isinstance(message, str):
                                await websocket.send_text(message)
                            else:
                                await websocket.send_bytes(message)
                    except Exception:
                        pass

                # Run both forwarding tasks concurrently
                tasks = [
                    asyncio.create_task(forward_to_internal()),
                    asyncio.create_task(forward_to_client()),
                ]

                # Wait for either task to complete (connection closed)
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel the other task
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        except Exception as e:
            logger.error(f"WebSocket proxy error: {e}")
            try:
                await websocket.close(code=1011, reason="Internal server error")
            except Exception:
                pass


def create_gateway_app(
    process_manager: "ProcessManager | None" = None,
    client_timeout: float = 30.0,
    client_dir: str | None = None,
) -> FastAPI:
    """
    Create a FastAPI app configured as a reverse proxy gateway.

    Args:
        process_manager: Optional ProcessManager for health monitoring.
        client_timeout: Timeout for proxied HTTP requests.
        client_dir: Optional path to the client build directory for static files.

    Returns:
        Configured FastAPI application.
    """
    router = GatewayRouter(process_manager=process_manager, client_timeout=client_timeout)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await router.startup()
        yield
        await router.shutdown()

    app = FastAPI(
        title="DevLabo Gateway",
        description="Reverse proxy gateway for DevLabo sandbox dev servers",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CORS middleware for browser requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health_check():
        """Gateway and process health check endpoint."""
        result = {"gateway": "ok"}

        if router.process_manager:
            result["processes"] = router.process_manager.get_all_status()

        return result

    @app.post("/agent/chat")
    async def agent_chat(request: Request):
        """
        Proxy chat requests to the AI agent.

        Expects JSON body with:
        - message: str - The user's message
        - context: optional dict with userId, projectId, activeModule
        """
        try:
            import modal

            body = await request.json()
            message = body.get("message", "")
            context = body.get("context", {})

            user_id = context.get("userId", "default")
            project_id = context.get("projectId", "default")

            # Get reference to the deployed DeepAgent
            AgentCls = modal.Cls.from_name("devlabo-agent", "DeepAgent")
            agent = AgentCls(user_id=user_id, project_id=project_id)

            # Call the chat method
            result = agent.chat.remote(message=message)

            return {
                "message": result.get("response", "No response"),
                "actions": [
                    {"type": "file_modified", "path": f}
                    for f in result.get("files_changed", [])
                ],
            }

        except Exception as e:
            logger.error(f"Agent chat error: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.api_route(
        "/connect/{user}/{project}/{module}/{path:path}",
        methods=PROXY_METHODS,
    )
    async def proxy_request(
        request: Request,
        user: str,
        project: str,
        module: str,
        path: str = "",
    ):
        """Proxy HTTP requests to internal dev servers."""
        return await router.proxy_http(request, user, project, module, path)

    @app.websocket("/connect/{user}/{project}/{module}/{path:path}")
    async def proxy_ws(
        websocket: WebSocket,
        user: str,
        project: str,
        module: str,
        path: str = "",
    ):
        """Proxy WebSocket connections to internal dev servers (for Vite HMR)."""
        await router.proxy_websocket(websocket, user, project, module, path)

    # Root path for modules (without trailing path)
    @app.api_route(
        "/connect/{user}/{project}/{module}",
        methods=PROXY_METHODS,
    )
    async def proxy_request_root(
        request: Request,
        user: str,
        project: str,
        module: str,
    ):
        """Proxy HTTP requests to internal dev server root."""
        return await router.proxy_http(request, user, project, module, "")

    @app.websocket("/connect/{user}/{project}/{module}")
    async def proxy_ws_root(
        websocket: WebSocket,
        user: str,
        project: str,
        module: str,
    ):
        """Proxy WebSocket connections to internal dev server root."""
        await router.proxy_websocket(websocket, user, project, module, "")

    # Mount static files for the client app if directory exists
    if client_dir:
        client_path = Path(client_dir)
        if client_path.is_dir():
            app.mount("/app", StaticFiles(directory=client_path, html=True), name="client")
            logger.info(f"Mounted client static files from {client_path}")

    return app

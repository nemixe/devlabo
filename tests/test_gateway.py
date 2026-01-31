"""Tests for the gateway router."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.router import (
    MODULE_PORTS,
    GatewayRouter,
    create_gateway_app,
    filter_headers,
)


class TestFilterHeaders:
    """Tests for the filter_headers function."""

    def test_removes_hop_by_hop_headers(self):
        """Test that hop-by-hop headers are removed."""
        headers = {
            "content-type": "application/json",
            "connection": "keep-alive",
            "keep-alive": "timeout=5",
            "transfer-encoding": "chunked",
            "x-custom": "value",
        }

        filtered = filter_headers(headers)

        assert "content-type" in filtered
        assert "x-custom" in filtered
        assert "connection" not in filtered
        assert "keep-alive" not in filtered
        assert "transfer-encoding" not in filtered

    def test_preserves_normal_headers(self):
        """Test that normal headers are preserved."""
        headers = {
            "content-type": "application/json",
            "authorization": "Bearer token",
            "x-custom-header": "value",
        }

        filtered = filter_headers(headers)

        assert filtered == headers

    def test_empty_headers(self):
        """Test filtering empty headers."""
        assert filter_headers({}) == {}


class TestModulePorts:
    """Tests for MODULE_PORTS configuration."""

    def test_all_modules_defined(self):
        """Test that all expected modules are defined."""
        expected = ["prototype", "frontend", "dbml", "tests"]
        for module in expected:
            assert module in MODULE_PORTS

    def test_unique_ports(self):
        """Test that all ports are unique."""
        ports = list(MODULE_PORTS.values())
        assert len(ports) == len(set(ports))

    def test_port_range(self):
        """Test that ports are in expected range."""
        for port in MODULE_PORTS.values():
            assert 3001 <= port <= 3004


class TestGatewayRouter:
    """Tests for GatewayRouter class."""

    @pytest.fixture
    def router(self):
        """Create a GatewayRouter instance."""
        return GatewayRouter()

    def test_init_default(self, router):
        """Test default initialization."""
        assert router.process_manager is None
        assert router.client_timeout == 30.0
        assert router._http_client is None

    def test_init_with_process_manager(self):
        """Test initialization with ProcessManager."""
        mock_pm = MagicMock()
        router = GatewayRouter(process_manager=mock_pm, client_timeout=60.0)

        assert router.process_manager is mock_pm
        assert router.client_timeout == 60.0

    @pytest.mark.asyncio
    async def test_startup_creates_client(self, router):
        """Test that startup creates an HTTP client."""
        await router.startup()

        try:
            assert router._http_client is not None
            assert isinstance(router._http_client, httpx.AsyncClient)
        finally:
            await router.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_closes_client(self, router):
        """Test that shutdown closes the HTTP client."""
        await router.startup()
        await router.shutdown()

        assert router._http_client is None

    def test_get_target_url_valid_module(self, router):
        """Test building target URL for valid modules."""
        url = router._get_target_url("prototype", "index.html", "")
        assert url == "http://127.0.0.1:3001/index.html"

        url = router._get_target_url("frontend", "src/main.js", "v=1")
        assert url == "http://127.0.0.1:3002/src/main.js?v=1"

    def test_get_target_url_invalid_module(self, router):
        """Test building target URL for invalid module raises HTTPException."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            router._get_target_url("invalid", "path", "")

        assert exc_info.value.status_code == 404
        assert "Unknown module" in exc_info.value.detail


class TestCreateGatewayApp:
    """Tests for create_gateway_app function."""

    def test_creates_fastapi_app(self):
        """Test that it creates a FastAPI app."""
        app = create_gateway_app()

        assert isinstance(app, FastAPI)
        assert app.title == "DevLabo Gateway"

    def test_health_endpoint_exists(self):
        """Test that health endpoint is registered."""
        app = create_gateway_app()
        routes = [r.path for r in app.routes]

        assert "/health" in routes

    def test_proxy_endpoints_exist(self):
        """Test that proxy endpoints are registered."""
        app = create_gateway_app()
        routes = [r.path for r in app.routes]

        assert "/connect/{user}/{project}/{module}/{path:path}" in routes
        assert "/connect/{user}/{project}/{module}" in routes


class TestGatewayAppIntegration:
    """Integration tests for the gateway app."""

    @pytest.fixture
    def app(self):
        """Create a test gateway app."""
        return create_gateway_app()

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test the health endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["gateway"] == "ok"

    def test_health_endpoint_with_process_manager(self):
        """Test health endpoint includes process status."""
        mock_pm = MagicMock()
        mock_pm.get_all_status.return_value = {
            "prototype": "running",
            "frontend": "stopped",
        }

        app = create_gateway_app(process_manager=mock_pm)
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "processes" in data
        assert data["processes"]["prototype"] == "running"
        assert data["processes"]["frontend"] == "stopped"

    def test_proxy_unknown_module_returns_404(self):
        """Test that unknown modules return 404."""
        app = create_gateway_app()
        # Need to use lifespan context manager for proper initialization
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/connect/user/project/unknown/path")

            assert response.status_code == 404
            assert "Unknown module" in response.json()["detail"]

    def test_proxy_connect_error_returns_502(self):
        """Test that connection errors return 502."""
        app = create_gateway_app()
        # Prototype server not running, should return 502
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/connect/user/project/prototype/index.html")

            assert response.status_code == 502
            assert "Cannot connect" in response.json()["detail"]


class TestGatewayProxyBehavior:
    """Tests for proxy behavior with mocked backends."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_proxy_forwards_headers(self):
        """Test that proxy forwards appropriate headers."""
        router = GatewayRouter()
        await router.startup()

        try:
            # Create mock request
            mock_request = MagicMock()
            mock_request.method = "GET"
            mock_request.headers = {"content-type": "application/json", "x-custom": "value"}
            mock_request.query_params = ""
            mock_request.client = MagicMock(host="192.168.1.1")
            mock_request.url = MagicMock(scheme="https")
            mock_request.body = AsyncMock(return_value=b"")

            # Mock the HTTP response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html"}
            mock_response.content = b"<html></html>"

            with patch.object(
                router._http_client, "request", new_callable=AsyncMock
            ) as mock_req:
                mock_req.return_value = mock_response

                await router.proxy_http(
                    mock_request, "user", "project", "prototype", "index.html"
                )

                # Verify request was made with correct parameters
                call_args = mock_req.call_args
                assert call_args.kwargs["method"] == "GET"
                assert "127.0.0.1:3001" in call_args.kwargs["url"]
                assert "x-forwarded-for" in call_args.kwargs["headers"]
                assert "x-devlabo-user" in call_args.kwargs["headers"]
                assert call_args.kwargs["headers"]["x-devlabo-user"] == "user"

        finally:
            await router.shutdown()

    @pytest.mark.asyncio
    async def test_proxy_preserves_response_status(self):
        """Test that proxy preserves response status code."""
        router = GatewayRouter()
        await router.startup()

        try:
            mock_request = MagicMock()
            mock_request.method = "GET"
            mock_request.headers = {}
            mock_request.query_params = ""
            mock_request.client = MagicMock(host="127.0.0.1")
            mock_request.url = MagicMock(scheme="http")
            mock_request.body = AsyncMock(return_value=b"")

            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.headers = {"content-type": "text/plain"}
            mock_response.content = b"Not Found"

            with patch.object(
                router._http_client, "request", new_callable=AsyncMock
            ) as mock_req:
                mock_req.return_value = mock_response

                response = await router.proxy_http(
                    mock_request, "user", "project", "frontend", "missing.js"
                )

                assert response.status_code == 404

        finally:
            await router.shutdown()

    @pytest.mark.asyncio
    async def test_proxy_handles_timeout(self):
        """Test that proxy handles timeouts correctly."""
        router = GatewayRouter(client_timeout=1.0)
        await router.startup()

        try:
            mock_request = MagicMock()
            mock_request.method = "GET"
            mock_request.headers = {}
            mock_request.query_params = ""
            mock_request.client = MagicMock(host="127.0.0.1")
            mock_request.url = MagicMock(scheme="http")
            mock_request.body = AsyncMock(return_value=b"")

            with patch.object(
                router._http_client, "request", new_callable=AsyncMock
            ) as mock_req:
                mock_req.side_effect = httpx.TimeoutException("Timeout")

                from fastapi import HTTPException

                with pytest.raises(HTTPException) as exc_info:
                    await router.proxy_http(
                        mock_request, "user", "project", "prototype", "slow"
                    )

                assert exc_info.value.status_code == 504
                assert "Timeout" in exc_info.value.detail

        finally:
            await router.shutdown()


class TestWebSocketProxy:
    """Tests for WebSocket proxy functionality."""

    @pytest.mark.asyncio
    async def test_websocket_invalid_module_closes_connection(self):
        """Test that invalid module closes WebSocket with error."""
        router = GatewayRouter()

        mock_websocket = AsyncMock()
        mock_websocket.query_params = ""

        await router.proxy_websocket(
            mock_websocket, "user", "project", "invalid", "path"
        )

        mock_websocket.close.assert_called_once()
        call_args = mock_websocket.close.call_args
        assert call_args.kwargs["code"] == 4004
        assert "Unknown module" in call_args.kwargs["reason"]

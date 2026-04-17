"""HTTP /health endpoint and Prometheus-compatible metrics exporter.

Provides a lightweight health check server that aggregates status
from all engine components.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


class HealthMonitor:
    """HTTP health check and metrics server.

    Registers component health_check callables and exposes them
    via HTTP GET /health and GET /metrics.

    Integration:
        - CONSOLE_HOOK: health_port, metrics_export_interval
        - DASHBOARD_HOOK: all metrics (this IS the metrics source)
    """

    def __init__(self, port: int = 9100) -> None:
        self._port = port
        self._components: Dict[str, Callable[[], Dict]] = {}
        self._start_time: float = time.monotonic()
        self._app: Optional[Any] = None
        self._runner: Optional[Any] = None
        self._custom_metrics: Dict[str, float] = {}

    def register(self, name: str, health_fn: Callable[[], Dict]) -> None:
        """Register a component health check function."""
        self._components[name] = health_fn

    def set_metric(self, name: str, value: float) -> None:
        """Set a custom metric value."""
        self._custom_metrics[name] = value

    def collect_all(self) -> Dict[str, Any]:
        """Collect health status from all registered components."""
        uptime = round(time.monotonic() - self._start_time, 1)
        status: Dict[str, Any] = {
            "status": "ok",
            "uptime_s": uptime,
            "components": {},
            "custom_metrics": dict(self._custom_metrics),
        }

        all_ok = True
        for name, fn in self._components.items():
            try:
                component_status = fn()
                status["components"][name] = component_status
            except Exception as e:
                status["components"][name] = {"error": str(e)}
                all_ok = False

        status["status"] = "ok" if all_ok else "degraded"
        return status

    async def start(self) -> None:
        """Start the HTTP health server."""
        if not HAS_AIOHTTP:
            return

        self._app = web.Application()
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/metrics", self._handle_metrics)
        self._app.router.add_get("/status", self._handle_health)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()

    async def stop(self) -> None:
        """Stop the HTTP health server."""
        if self._runner:
            await self._runner.cleanup()

    async def _handle_health(self, request: Any) -> Any:
        """Handle GET /health."""
        data = self.collect_all()
        http_status = 200 if data["status"] == "ok" else 503
        return web.json_response(data, status=http_status)

    async def _handle_metrics(self, request: Any) -> Any:
        """Handle GET /metrics — Prometheus text format."""
        data = self.collect_all()
        lines = [
            "# HELP zangetsu_uptime_seconds Engine uptime",
            "# TYPE zangetsu_uptime_seconds gauge",
            "zangetsu_uptime_seconds " + str(data["uptime_s"]),
        ]

        for metric_name, value in self._custom_metrics.items():
            safe_name = metric_name.replace(".", "_").replace("-", "_")
            lines.append("zangetsu_" + safe_name + " " + str(value))

        return web.Response(text="\n".join(lines) + "\n", content_type="text/plain")

    # DASHBOARD_HOOK: health_overview
    def health_check(self) -> Dict:
        return {
            "port": self._port,
            "registered_components": list(self._components.keys()),
            "uptime_s": round(time.monotonic() - self._start_time, 1),
            "aiohttp_available": HAS_AIOHTTP,
        }

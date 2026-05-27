"""API logging middleware"""
from __future__ import annotations

import time
import json
import asyncio
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog

logger = structlog.get_logger()


class APILoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every API call to the database"""

    # Paths to exclude from logging
    EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Skip excluded paths
        if path in self.EXCLUDED_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        start_time = time.time()
        method = request.method
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        user_id = None
        thread_id = request.headers.get("x-thread-id") or request.headers.get("x-chat-id")

        # Try to get user_id from auth header (Bearer token is parsed loosely)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # We'll log the presence of auth but not decode JWT here
            user_id = "authenticated"

        # Call the actual endpoint
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Get response status
        response_status = response.status_code

        # Log asynchronously (fire-and-forget)
        asyncio.create_task(
            self._save_log(
                method=method,
                path=path,
                request_body=None,
                response_status=response_status,
                response_body=None,
                duration_ms=duration_ms,
                user_id=user_id,
                thread_id=thread_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )

        return response

    async def _save_log(
        self,
        method: str,
        path: str,
        request_body: dict | str | None,
        response_status: int,
        response_body: dict | None,
        duration_ms: float,
        user_id: str | None,
        thread_id: str | None,
        ip_address: str | None,
        user_agent: str,
    ):
        """Persist log entry to database"""
        try:
            from app.db.repositories.api_call_log import APICallLogRepository

            await APICallLogRepository.create({
                "method": method,
                "path": path,
                "request_body": request_body,
                "response_status": response_status,
                "response_body": response_body,
                "duration_ms": duration_ms,
                "user_id": user_id,
                "thread_id": thread_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
            })
        except Exception as e:
            logger.warning("api_log_save_failed", error=str(e), path=path)
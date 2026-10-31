import asyncio
import logging
from typing import Optional

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class InFlightRequests:
    def __init__(self) -> None:
        self._count = 0
        self._drained = asyncio.Event()
        self._drained.set()

    @property
    def count(self) -> int:
        return self._count

    def _acquire(self) -> None:
        self._count += 1
        self._drained.clear()

    def _release(self) -> None:
        self._count -= 1
        if self._count <= 0:
            self._count = 0
            self._drained.set()

    async def drain(self, timeout: Optional[float] = None) -> bool:
        if self._count == 0:
            return True

        logger.info(f"Waiting for {self._count} in-flight request(s) to complete...")

        try:
            await asyncio.wait_for(self._drained.wait(), timeout=timeout)
            logger.info("All in-flight requests completed")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Timed out waiting for {self._count} in-flight request(s)")
            return False


class InFlightMiddleware:
    def __init__(self, app: ASGIApp, tracker: InFlightRequests) -> None:
        self.app = app
        self.tracker = tracker

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        self.tracker._acquire()
        try:
            await self.app(scope, receive, send)
        finally:
            self.tracker._release()

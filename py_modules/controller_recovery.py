"""Bounded reconciliation after startup, profile changes, and resume."""

import asyncio
import logging


class ControllerRecovery:
    # Keep checking after an early success: SteamOS may recreate targets later.
    DELAYS = (0, 1, 2, 4, 8, 15)

    def __init__(self, sync, logger=None):
        self.sync = sync
        self.logger = logger or logging.getLogger(__name__)
        self.task = None
        self.game_id = "default"
        self.suspended = False
        self.closed = False

    def request(self, game_id):
        self.game_id = game_id or "default"
        self.cancel()
        if not self.suspended and not self.closed:
            self.task = asyncio.create_task(self._run())

    async def _run(self):
        refresh_mappings = True
        for delay in self.DELAYS:
            await asyncio.sleep(delay)
            try:
                self.sync(self.game_id, refresh_mappings=refresh_mappings)
                refresh_mappings = False
            except Exception:
                self.logger.warning("Controller recovery attempt failed", exc_info=True)
                # Retry mappings too if the controller was unavailable.
                refresh_mappings = True

    def cancel(self):
        if self.task and not self.task.done():
            self.task.cancel()

    def suspend(self):
        self.suspended = True
        self.cancel()

    def resume(self, game_id):
        self.suspended = False
        self.request(game_id)

    async def close(self):
        self.closed = True
        self.cancel()
        if self.task:
            try:
                await self.task
            except asyncio.CancelledError:
                pass

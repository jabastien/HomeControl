"""The core instance for HomeControl"""

import argparse
import asyncio
import logging
import os
import signal
from contextlib import suppress
from typing import Optional

from homecontrol.const import (EVENT_CORE_BOOTSTRAP_COMPLETE, EXIT_RESTART,
                               EXIT_SHUTDOWN)
from homecontrol.dependencies.config_manager import ConfigManager
from homecontrol.dependencies.event_bus import EventBus
from homecontrol.dependencies.item_manager import ItemManager
from homecontrol.dependencies.module_manager import ModuleManager
from homecontrol.dependencies.uuid import get_uuid

LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
class Core:
    """
    Represents the root object for HomeControl
    """

    # pylint: disable=too-many-arguments
    def __init__(self,
                 cfg: dict,
                 cfg_file: str,
                 loop: Optional[asyncio.AbstractEventLoop] = None,
                 start_args: Optional[argparse.Namespace] = None) -> None:
        """
        :param cfg: config dictionary
        :param cfg_file: configuration file
        :param loop: asyncio EventLoop
        :param start_args: start parameters
        """
        self.start_args = start_args or argparse.Namespace()
        self.loop = loop or asyncio.get_event_loop()
        self.cfg = ConfigManager(cfg, cfg_file)
        self.cfg_path = cfg_file
        self.cfg_dir = os.path.dirname(cfg_file)
        self.block_future = asyncio.Future()
        self.event_bus = EventBus(core=self)
        self.module_manager = ModuleManager(core=self)
        self.modules = self.module_manager.module_accessor
        self.item_manager = ItemManager(core=self)
        self.uuid = get_uuid(self)

    async def bootstrap(self) -> None:
        """
        Startup coroutine for Core
        """
        if not os.name == "nt":  # Windows does not have signals
            self.loop.add_signal_handler(signal.SIGINT, self.shutdown)
            self.loop.add_signal_handler(signal.SIGTERM, self.shutdown)
        else:
            # Windows needs its special signal handling
            signal.signal(signal.SIGINT, self.shutdown)
            signal.signal(signal.SIGTERM, self.shutdown)

        # Load modules
        await self.module_manager.init()

        # Init items
        self.loop.create_task(self.item_manager.init())

        self.event_bus.broadcast(EVENT_CORE_BOOTSTRAP_COMPLETE)
        LOGGER.info("Core bootstrap complete")

    async def block_until_stop(self) -> int:
        """
        Blocking method to keep HomeControl running
        until Core.block_future is done

        Also triggers the stop coroutine when block_future has a result
        """
        with suppress(asyncio.CancelledError):
            exit_return = await self.block_future

        await self.stop()
        return exit_return

    async def stop(self) -> None:
        """Stops HomeControl"""
        LOGGER.warning("Shutting Down")
        await self.item_manager.stop()
        await self.module_manager.stop()

        pending = [task
                   for task
                   in asyncio.all_tasks(loop=self.loop)
                   if task is not asyncio.current_task(loop=self.loop)]

        if pending:
            LOGGER.info("Waiting for pending tasks (1s)")
            await asyncio.wait(pending, loop=self.loop, timeout=1)

        LOGGER.warning("Closing the loop soon")
        self.loop.call_soon(self.loop.stop)

    def restart(self) -> None:
        """Restarts HomeControl"""
        self.block_future.set_result(EXIT_RESTART)

    def shutdown(self) -> None:
        """Shuts HomeControl down"""
        self.block_future.set_result(EXIT_SHUTDOWN)

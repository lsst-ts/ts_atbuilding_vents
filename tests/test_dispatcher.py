import asyncio
import logging
import unittest
from unittest.mock import patch, MagicMock

from lsst.ts import tcpip
from lsst.ts.vent.controller import Controller, Dispatcher

# Standard timeout for TCP/IP messages (sec).
TCP_TIMEOUT = 1

class TestDispatcher(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
         self.log = logging.getLogger()

         # Mock the controller
         self.patcher = patch("lsst.ts.vent.controller.Controller")
         MockClass = self.patcher.start()
         self.mock_controller = MockClass.return_value

         # Build the dispatcher and wait for it to listen
         self.dispatcher = Dispatcher(port=1234, log=self.log, controller=self.mock_controller)
         await self.dispatcher.start_task

         # Connect to the dispatcher
         self.client = tcpip.Client(host=self.dispatcher.host, port=self.dispatcher.port,
                                    log=self.dispatcher.log,)
         await self.client.start_task
         await self.dispatcher.connected_task

    async def asyncTearDown(self):
        await self.client.close()
        await self.dispatcher.close()
        self.patcher.stop()

    async def send_and_receive(self, message: str) -> str:
        await asyncio.wait_for(self.client.write_str(message + "\r\n"), timeout=TCP_TIMEOUT)
        response = await asyncio.wait_for(self.client.read_str(), timeout=TCP_TIMEOUT)
        return response

    async def test_ping(self):
        """Check basic functionality with a ping command."""
        self.assertEqual(await self.send_and_receive("ping"), "ping OK")

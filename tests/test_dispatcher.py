import asyncio
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from lsst.ts import tcpip
from lsst.ts.vent.controller import Dispatcher

# Standard timeout for TCP/IP messages (sec).
TCP_TIMEOUT = 1


class TestDispatcher(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.log = logging.getLogger()

        # Mock the controller
        self.patcher = patch("lsst.ts.vent.controller.Controller")
        MockClass = self.patcher.start()
        self.mock_controller = MockClass.return_value
        self.mock_controller.get_fan_manual_control = AsyncMock()
        self.mock_controller.fan_manual_control = AsyncMock()
        self.mock_controller.start_fan = AsyncMock()
        self.mock_controller.stop_fan = AsyncMock()
        self.mock_controller.get_fan_frequency = AsyncMock()
        self.mock_controller.set_fan_frequency = AsyncMock()
        self.mock_controller.vfd_fault_reset = AsyncMock()
        self.mock_controller.last8faults = AsyncMock()
        self.mock_controller.vent_open = MagicMock()
        self.mock_controller.vent_close = MagicMock()
        self.mock_controller.vent_state = MagicMock()

        # Build the dispatcher and wait for it to listen
        self.dispatcher = Dispatcher(
            port=1234, log=self.log, controller=self.mock_controller
        )
        await self.dispatcher.start_task

        # Connect to the dispatcher
        self.client = tcpip.Client(
            host=self.dispatcher.host,
            port=self.dispatcher.port,
            log=self.dispatcher.log,
        )
        await self.client.start_task
        await self.dispatcher.connected_task

    async def asyncTearDown(self):
        await self.client.close()
        await self.dispatcher.close()
        self.patcher.stop()

    async def send_and_receive(self, message: str) -> str:
        await asyncio.wait_for(
            self.client.write_str(message + "\r\n"), timeout=TCP_TIMEOUT
        )
        response = await asyncio.wait_for(self.client.read_str(), timeout=TCP_TIMEOUT)
        response = response.strip()
        return response

    async def test_ping(self):
        """Check basic functionality with a ping command."""
        self.assertEqual(await self.send_and_receive("ping"), "ping OK")

    async def test_closeVentGate(self):
        """Test closeVentGate command."""
        self.assertEqual(
            await self.send_and_receive("closeVentGate 123"), "closeVentGate OK"
        )
        self.mock_controller.vent_close.assert_called_once_with(123)

    async def test_openVentGate(self):
        """Test openVentGate command."""
        self.assertEqual(
            await self.send_and_receive("openVentGate 234"), "openVentGate OK"
        )
        self.mock_controller.vent_open.assert_called_once_with(234)

    async def test_resetExtractionFanDrive(self):
        """Test resetExtractionFanDrive command."""
        self.assertEqual(
            await self.send_and_receive("resetExtractionFanDrive"),
            "resetExtractionFanDrive OK",
        )
        self.mock_controller.vfd_fault_reset.assert_called_once_with()

    async def test_setExtractionFanDriveFreq(self):
        """Test setExtractionFanDriveFreq command."""
        self.assertEqual(
            await self.send_and_receive("setExtractionFanDriveFreq 22.5"),
            "setExtractionFanDriveFreq OK",
        )
        self.mock_controller.set_fan_frequency.assert_called_once_with(22.5)

    async def test_setExtractionFanManualControlMode_true(self):
        """Test setExtractionFanManualControlMode with argument True."""
        self.assertEqual(
            await self.send_and_receive("setExtractionFanManualControlMode True"),
            "setExtractionFanManualControlMode OK",
        )
        self.mock_controller.fan_manual_control.assert_called_once_with(True)

    async def test_setExtractionFanManualControlMode_false(self):
        """Test setExtractionFanManualControlMode with argument False."""
        self.assertEqual(
            await self.send_and_receive("setExtractionFanManualControlMode False"),
            "setExtractionFanManualControlMode OK",
        )
        self.mock_controller.fan_manual_control.assert_called_once_with(False)

    async def test_startExtractionFan(self):
        """Test startExtractionFan command."""
        self.assertEqual(
            await self.send_and_receive("startExtractionFan"), "startExtractionFan OK"
        )
        self.mock_controller.start_fan.assert_called_once_with()

    async def test_stopExtractionFan(self):
        """Test stopExtractionFan command."""
        self.assertEqual(
            await self.send_and_receive("stopExtractionFan"), "stopExtractionFan OK"
        )
        self.mock_controller.stop_fan.assert_called_once_with()

    async def test_badcommand(self):
        """Test with an invalid command."""
        self.assertEqual(
            await self.send_and_receive("thisisnotacommand"),
            "thisisnotacommand raise NotImplementedError()",
        )

    async def test_wrongargumenttype(self):
        """Test with incorrect argument types."""
        response = await self.send_and_receive("closeVentGate 0.5")
        self.assertTrue("closeVentGate raise ValueError(" in response)

    async def test_wrongargumentcount(self):
        """Test for incorrect number of arguments."""
        response = await self.send_and_receive("closeVentGate")
        self.assertEqual(
            response,
            "closeVentGate raise TypeError('closeVentGate expected 1 arguments')",
        )

        response = await self.send_and_receive("openVentGate 1 2 3")
        self.assertEqual(
            response,
            "openVentGate raise TypeError('openVentGate expected 1 arguments')",
        )

        response = await self.send_and_receive("ping 3.14159")
        self.assertEqual(response, "ping raise TypeError('ping expected 0 arguments')")

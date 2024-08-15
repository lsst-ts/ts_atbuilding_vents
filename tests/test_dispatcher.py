# This file is part of ts_atbuilding_vents
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import json
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

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

    def check_response(
        self, response: str, expected_command: str, expected_error: str | None = None
    ) -> dict:
        json_data = json.loads(response)
        self.assertEqual(json_data["command"], expected_command)
        if expected_error is None:
            self.assertEqual(json_data["error"], 0)
        else:
            self.assertNotEqual(json_data["error"], 0)
            self.assertEqual(json_data["exception_name"], expected_error)
            self.assertTrue("message" in json_data)

    async def test_ping(self):
        """Check basic functionality with a ping command."""
        response = await self.send_and_receive("ping")
        self.check_response(response, "ping")

    async def test_close_vent_gate(self):
        """Test close_vent_gate command."""
        response = await self.send_and_receive("close_vent_gate 1 -1 -1 -1")
        self.check_response(response, "close_vent_gate")
        self.mock_controller.vent_close.assert_called_once_with(1)

    async def test_open_vent_gate(self):
        """Test open_vent_gate command."""
        response = await self.send_and_receive("open_vent_gate 2 -1 -1 -1")
        self.check_response(response, "open_vent_gate")
        self.mock_controller.vent_open.assert_called_once_with(2)

    async def test_close_vent_multiple(self):
        """Test close_vent_gate command sending it multiple gates."""
        response = await self.send_and_receive("close_vent_gate 1 2 3 -1")
        self.check_response(response, "close_vent_gate")
        self.mock_controller.vent_close.assert_has_calls(
            [call(1), call(2), call(3)], any_order=False
        )

    async def test_open_vent_multiple(self):
        """Test open_vent_gate command sending it multiple gates."""
        response = await self.send_and_receive("open_vent_gate -1 1 2 3")
        self.check_response(response, "open_vent_gate")
        self.mock_controller.vent_open.assert_has_calls(
            [call(1), call(2), call(3)], any_order=False
        )

    async def test_reset_extraction_fan_drive(self):
        """Test reset_extraction_fan_drive command."""
        response = await self.send_and_receive("reset_extraction_fan_drive")
        self.check_response(response, "reset_extraction_fan_drive")
        self.mock_controller.vfd_fault_reset.assert_called_once_with()

    async def test_set_extraction_fan_drive_freq(self):
        """Test set_extraction_fan_drive_freq command."""
        response = await self.send_and_receive("set_extraction_fan_drive_freq 22.5")
        self.check_response(response, "set_extraction_fan_drive_freq")
        self.mock_controller.set_fan_frequency.assert_called_once_with(22.5)

    async def test_set_extraction_fan_manual_control_mode_true(self):
        """Test setExtractionFanManualControlMode with argument True."""
        response = await self.send_and_receive(
            "set_extraction_fan_manual_control_mode True"
        )
        self.check_response(response, "set_extraction_fan_manual_control_mode")
        self.mock_controller.fan_manual_control.assert_called_once_with(True)

    async def test_set_extraction_fan_manual_control_mode_false(self):
        """Test set_extraction_fan_manual_control_mode with argument False."""
        response = await self.send_and_receive(
            "set_extraction_fan_manual_control_mode False"
        )
        self.check_response(response, "set_extraction_fan_manual_control_mode")
        self.mock_controller.fan_manual_control.assert_called_once_with(False)

    async def test_start_extraction_fan(self):
        """Test start_extraction_fan command."""
        response = await self.send_and_receive("start_extraction_fan")
        self.check_response(response, "start_extraction_fan")
        self.mock_controller.start_fan.assert_called_once_with()

    async def test_stop_extraction_fan(self):
        """Test stop_extraction_fan command."""
        response = await self.send_and_receive("stop_extraction_fan")
        self.check_response(response, "stop_extraction_fan")
        self.mock_controller.stop_fan.assert_called_once_with()

    async def test_badcommand(self):
        """Test with an invalid command."""
        response = await self.send_and_receive("thisisnotacommand")
        self.check_response(response, "thisisnotacommand", "NotImplementedError")

    async def test_wrongargumenttype(self):
        """Test with incorrect argument types."""
        response = await self.send_and_receive("close_vent_gate 0.5 0.5 0.5 0.5")
        self.check_response(response, "close_vent_gate", "ValueError")

    async def test_wrongargumentcount(self):
        """Test for incorrect number of arguments."""
        response = await self.send_and_receive("close_vent_gate")
        self.check_response(response, "close_vent_gate", "TypeError")

        response = await self.send_and_receive("open_vent_gate 1 2 3")
        self.check_response(response, "open_vent_gate", "TypeError")

        response = await self.send_and_receive("ping 3.14159")
        self.check_response(response, "ping", "TypeError")

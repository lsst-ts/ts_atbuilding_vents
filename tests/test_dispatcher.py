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
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from lsst.ts import tcpip
from lsst.ts.vent.controller import Dispatcher
from lsst.ts.xml.enums.ATBuilding import FanDriveState

# Standard timeout for TCP/IP messages (sec).
TCP_TIMEOUT = 10


class TestDispatcher(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.log = logging.getLogger()

        # Mock the controller
        self.patcher = patch("lsst.ts.vent.controller.Controller")
        MockClass = self.patcher.start()
        self.mock_controller = MockClass.return_value
        self.mock_controller.get_fan_manual_control = AsyncMock()
        self.mock_controller.get_max_frequency = MagicMock(return_value=123.4)
        self.mock_controller.get_drive_voltage = AsyncMock(return_value=382.9)
        self.mock_controller.fan_manual_control = AsyncMock()
        self.mock_controller.start_fan = AsyncMock()
        self.mock_controller.stop_fan = AsyncMock()
        self.mock_controller.get_fan_frequency = AsyncMock()
        self.mock_controller.set_fan_frequency = AsyncMock()
        self.mock_controller.vfd_fault_reset = AsyncMock()
        self.mock_controller.last8faults = AsyncMock()
        self.mock_controller.get_drive_state = AsyncMock()
        self.mock_controller.vent_open = MagicMock()
        self.mock_controller.vent_close = MagicMock()
        self.mock_controller.vent_state = MagicMock()

        self.mock_controller.get_fan_manual_control.return_value = False
        self.mock_controller.get_fan_frequency.return_value = 0.0
        self.mock_controller.last8faults.return_value = [
            (22, "Description of error")
        ] * 8
        self.mock_controller.vent_state.return_value = 0
        self.mock_controller.get_drive_state.return_value = FanDriveState.STOPPED

        # Build the dispatcher and wait for it to listen
        self.dispatcher = Dispatcher(
            port=1234, log=self.log, controller=self.mock_controller
        )
        self.dispatcher.TELEMETRY_INTERVAL = 5
        await self.dispatcher.start_task

        # Connect to the dispatcher
        self.client = tcpip.Client(
            host=self.dispatcher.host,
            port=self.dispatcher.port,
            log=self.dispatcher.log,
        )
        await self.client.start_task
        await self.dispatcher.connected_task

    async def asyncTearDown(self) -> None:
        await self.client.close()
        await self.dispatcher.close()
        self.patcher.stop()

    async def send_and_receive(
        self, message: str, pass_event: str | None = None, pass_telemetry: bool = False
    ) -> str:
        await asyncio.wait_for(
            self.client.write_str(message + "\r\n"), timeout=TCP_TIMEOUT
        )
        for i in range(1000):
            response = await asyncio.wait_for(
                self.client.read_str(), timeout=TCP_TIMEOUT
            )
            if "evt_" in response:
                if pass_event is not None and pass_event in response:
                    break
            elif "tel_" in response:
                if pass_telemetry:
                    break
            else:
                break

        response = response.strip()
        return response

    def check_response(
        self, response: str, expected_command: str, expected_error: str | None = None
    ) -> dict[str, Any]:
        json_data = json.loads(response)
        self.assertEqual(json_data["command"], expected_command)
        if expected_error is None:
            self.assertEqual(json_data["error"], 0)
        else:
            self.assertNotEqual(json_data["error"], 0)
            self.assertEqual(json_data["exception_name"], expected_error)
            self.assertTrue("message" in json_data)

        return json_data

    async def test_ping(self) -> None:
        """Check basic functionality with a ping command."""
        response = await self.send_and_receive("ping")
        self.check_response(response, "ping")

    async def test_close_vent_gate(self) -> None:
        """Test close_vent_gate command."""
        response = await self.send_and_receive("close_vent_gate 1 -1 -1 -1")
        self.check_response(response, "close_vent_gate")
        self.mock_controller.vent_close.assert_called_once_with(1)

    async def test_open_vent_gate(self) -> None:
        """Test open_vent_gate command."""
        response = await self.send_and_receive("open_vent_gate 2 -1 -1 -1")
        self.check_response(response, "open_vent_gate")
        self.mock_controller.vent_open.assert_called_once_with(2)

    async def test_close_vent_multiple(self) -> None:
        """Test close_vent_gate command sending it multiple gates."""
        response = await self.send_and_receive("close_vent_gate 1 2 3 -1")
        self.check_response(response, "close_vent_gate")
        self.mock_controller.vent_close.assert_has_calls(
            [call(1), call(2), call(3)], any_order=False
        )

    async def test_open_vent_multiple(self) -> None:
        """Test open_vent_gate command sending it multiple gates."""
        response = await self.send_and_receive("open_vent_gate -1 1 2 3")
        self.check_response(response, "open_vent_gate")
        self.mock_controller.vent_open.assert_has_calls(
            [call(1), call(2), call(3)], any_order=False
        )

    async def test_reset_extraction_fan_drive(self) -> None:
        """Test reset_extraction_fan_drive command."""
        response = await self.send_and_receive("reset_extraction_fan_drive")
        self.check_response(response, "reset_extraction_fan_drive")
        self.mock_controller.vfd_fault_reset.assert_called_once_with()

    async def test_set_extraction_fan_drive_freq(self) -> None:
        """Test set_extraction_fan_drive_freq command."""
        response = await self.send_and_receive("set_extraction_fan_drive_freq 22.5")
        self.check_response(response, "set_extraction_fan_drive_freq")
        self.mock_controller.set_fan_frequency.assert_called_once_with(22.5)

    async def test_set_extraction_fan_manual_control_mode_true(self) -> None:
        """Test setExtractionFanManualControlMode with argument True."""
        response = await self.send_and_receive(
            "set_extraction_fan_manual_control_mode True"
        )
        self.check_response(response, "set_extraction_fan_manual_control_mode")
        self.mock_controller.fan_manual_control.assert_called_once_with(True)

    async def test_set_extraction_fan_manual_control_mode_false(self) -> None:
        """Test set_extraction_fan_manual_control_mode with argument False."""
        response = await self.send_and_receive(
            "set_extraction_fan_manual_control_mode False"
        )
        self.check_response(response, "set_extraction_fan_manual_control_mode")
        self.mock_controller.fan_manual_control.assert_called_once_with(False)

    async def test_start_extraction_fan(self) -> None:
        """Test start_extraction_fan command."""
        response = await self.send_and_receive("start_extraction_fan")
        self.check_response(response, "start_extraction_fan")
        self.mock_controller.start_fan.assert_called_once_with()

    async def test_stop_extraction_fan(self) -> None:
        """Test stop_extraction_fan command."""
        response = await self.send_and_receive("stop_extraction_fan")
        self.check_response(response, "stop_extraction_fan")
        self.mock_controller.stop_fan.assert_called_once_with()

    async def test_badcommand(self) -> None:
        """Test with an invalid command."""
        response = await self.send_and_receive("thisisnotacommand")
        self.check_response(response, "thisisnotacommand", "NotImplementedError")

    async def test_wrongargumenttype(self) -> None:
        """Test with incorrect argument types."""
        response = await self.send_and_receive("close_vent_gate 0.5 0.5 0.5 0.5")
        self.check_response(response, "close_vent_gate", "ValueError")

    async def test_wrongargumentcount(self) -> None:
        """Test for incorrect number of arguments."""
        response = await self.send_and_receive("close_vent_gate")
        self.check_response(response, "close_vent_gate", "TypeError")

        response = await self.send_and_receive("open_vent_gate 1 2 3")
        self.check_response(response, "open_vent_gate", "TypeError")

        response = await self.send_and_receive("ping 3.14159")
        self.check_response(response, "ping", "TypeError")

    async def test_telemetry(self) -> None:
        """Test that telemetry is sent from time to time."""
        response = await self.send_and_receive("", pass_telemetry=True)
        self.check_response(response, "telemetry")
        response = await self.send_and_receive("", pass_telemetry=True)
        json_data = self.check_response(response, "telemetry")

        assert "tel_extraction_fan" in json_data["data"]
        assert "tel_drive_voltage" in json_data["data"]

        self.assertAlmostEqual(json_data["data"]["tel_extraction_fan"], 0.0)
        self.assertAlmostEqual(json_data["data"]["tel_drive_voltage"], 382.9, places=2)

    async def test_get_maximum_frequency(self) -> None:
        response = await self.send_and_receive("get_fan_drive_max_frequency")
        json_data = self.check_response(response, "get_fan_drive_max_frequency")
        self.assertAlmostEqual(json_data["return_value"], 123.4, places=1)

    async def test_gate_event(self) -> None:
        """Test that an event is emitted when the gate state changes."""
        gate_state = [self.mock_controller.vent_state.return_value] * 4
        response = await self.send_and_receive("", pass_event="evt_vent_gate_state")
        response_json = json.loads(response)
        self.assertEqual(response_json["data"], gate_state)

        self.mock_controller.vent_state.return_value = 1
        gate_state = [self.mock_controller.vent_state.return_value] * 4
        response = await self.send_and_receive("", pass_event="evt_vent_gate_state")
        response_json = json.loads(response)
        self.assertEqual(response_json["data"], gate_state)

    async def test_drive_fault(self) -> None:
        """Test that a drive fault is emitted."""
        fault_code = self.mock_controller.last8faults.return_value[0][0]
        response = await self.send_and_receive(
            "", pass_event="evt_extraction_fan_drive_fault_code"
        )
        response_json = json.loads(response)
        self.assertEqual(response_json["data"], fault_code)

        self.mock_controller.last8faults.return_value = [
            (123, "Description of error")
        ] * 8
        fault_code = self.mock_controller.last8faults.return_value[0][0]
        response = await self.send_and_receive(
            "", pass_event="evt_extraction_fan_drive_fault_code"
        )
        response_json = json.loads(response)
        self.assertEqual(response_json["data"], fault_code)

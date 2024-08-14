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

from lsst.ts import tcpip
from lsst.ts.vent.controller import (Config, Controller, Dispatcher,
                                     VentGateState)

# Standard timeout for TCP/IP messages (sec).
TCP_TIMEOUT = 1


class TestFull(unittest.IsolatedAsyncioTestCase):
    """Identical to the dispatcher test but without mocking."""

    async def asyncSetUp(self):
        print("TestFull.asyncSetUp")
        self.log = logging.getLogger()

        # Build the simulation controller and the dispatcher
        cfg = Config()
        cfg.hostname = "localhost"
        cfg.port = 26034
        self.controller = Controller(cfg, simulate=True)
        await self.controller.connect()

        self.dispatcher = Dispatcher(
            port=1234, log=self.log, controller=self.controller
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
        print("TestFull.asyncTearDown")
        await self.client.close()
        await self.dispatcher.close()
        await self.controller.stop()

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
        print(f"{response=}")
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

    async def test_vent_open(self):
        response = await self.send_and_receive("open_vent_gate 0")
        self.check_response(response, "open_vent_gate")
        self.assertEqual(self.controller.vent_state(0), VentGateState.OPEN)

    async def test_vent_close(self):
        response = await self.send_and_receive("close_vent_gate 0")
        self.check_response(response, "close_vent_gate")
        self.assertEqual(self.controller.vent_state(0), VentGateState.CLOSED)

    async def test_invalid_vent(self):
        response = await self.send_and_receive("open_vent_gate 456")
        self.check_response(response, "open_vent_gate", "ValueError")
        response = await self.send_and_receive("close_vent_gate 123")
        self.check_response(response, "close_vent_gate", "ValueError")

    async def test_fan_manual(self):
        response = await self.send_and_receive(
            "set_extraction_fan_manual_control_mode True"
        )
        self.check_response(response, "set_extraction_fan_manual_control_mode")
        response = await self.send_and_receive(
            "set_extraction_fan_manual_control_mode False"
        )
        self.check_response(response, "set_extraction_fan_manual_control_mode")
        response = await self.send_and_receive(
            "set_extraction_fan_manual_control_mode Nachos"
        )
        self.check_response(
            response, "set_extraction_fan_manual_control_mode", "ValueError"
        )
        response = await self.send_and_receive(
            "set_extraction_fan_manual_control_mode sour cream"
        )
        self.check_response(
            response, "set_extraction_fan_manual_control_mode", "TypeError"
        )

    async def test_start_fan(self):
        response = await self.send_and_receive("start_extraction_fan")
        self.check_response(response, "start_extraction_fan")

    async def test_stop_fan(self):
        response = await self.send_and_receive("start_extraction_fan")
        self.check_response(response, "start_extraction_fan")

    async def test_set_fan_frequency(self):
        response = await self.send_and_receive("set_extraction_fan_drive_freq 12.5")
        self.check_response(response, "set_extraction_fan_drive_freq")

    async def test_fault_recover(self):
        response = await self.send_and_receive("reset_extraction_fan_drive")
        self.check_response(response, "reset_extraction_fan_drive")

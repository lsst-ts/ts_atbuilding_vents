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
import os
import unittest

from lsst.ts.vent.controller import Controller
from pymodbus.server import ModbusSimulatorServer


class TestVfd(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        os.environ["VFD_HOSTNAME"] = "localhost"
        os.environ["VFD_PORT"] = "26034"

        self.loop = asyncio.new_event_loop()
        self.simulator = ModbusSimulatorServer(
            modbus_server="server",
            modbus_device="device",
            http_host="localhost",
            http_port=25074,
            json_file=os.path.dirname(__file__) + "/setup.json",
        )
        await self.simulator.run_forever(only_start=True)

        self.controller = Controller()
        await self.controller.connect()

    async def asyncTearDown(self):
        await self.simulator.stop()

    async def test_vfd_manual(self):
        self.assertTrue(self.controller.vfd_manual_control, "Simulated VFD expected to start in manual mode")
        await self.controller.vfd_manual_control(False)
        self.assertFalse(
            await self.controller.get_vfd_manual_control(),
            "set_vfd_manual_control should change VFD state (to False)",
        )
        await self.controller.vfd_manual_control(True)
        self.assertTrue(
            await self.controller.get_vfd_manual_control(),
            "set_vfd_manual_control should change VFD state (to True)",
        )

    async def test_vfd_start_fan(self):
        self.assertEqual(
            0.0, await self.controller.get_fan_frequency(), "Simulated VFD expected to start with fan at zero"
        )
        await self.controller.start_fan()
        self.assertEqual(
            self.controller.default_fan_frequency,
            await self.controller.get_fan_frequency(),
            "start_fan should change fan frequency to default value",
        )

    async def test_vfd_stop_fan(self):
        await self.controller.start_fan()
        self.assertNotEqual(
            0.0, await self.controller.get_fan_frequency(), "start_fan should have started the fan"
        )
        await self.controller.stop_fan()
        self.assertEqual(
            0.0, await self.controller.get_fan_frequency(), "stop_fan should change fan frequency to 0.0"
        )

    async def test_vfd_set_fan_frequency(self):
        await self.controller.start_fan()
        self.assertNotEqual(
            0.0, await self.controller.get_fan_frequency(), "start_fan should have started the fan"
        )
        target_frequency = self.controller.default_fan_frequency / 2
        await self.controller.set_fan_frequency(target_frequency)
        self.assertAlmostEqual(
            target_frequency,
            await self.controller.get_fan_frequency(),
            places=1,
            msg="set_fan_frequency should change fan frequency to 50.0",
        )

    async def test_fault_recover(self):
        r = await self.controller.vfd_fault_reset()
        self.assertIsNone(r)  # Yay I guess

    async def test_last8faults(self):
        last8 = await self.controller.last8faults()
        self.assertEqual(len(last8), 8, "last8faults should return 8 elements")
        for i, s in last8:
            self.assertIsInstance(i, int)
            self.assertIsInstance(s, str)
            self.assertEqual(i, 22)
            self.assertTrue("undervolt" in s)

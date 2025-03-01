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

import unittest

from lsst.ts.vent.controller import Config, Controller


class TestFan(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        cfg = Config()
        cfg.hostname = "localhost"
        cfg.port = 26034
        self.controller = Controller(cfg, simulate=True)
        await self.controller.connect()

    async def asyncTearDown(self) -> None:
        await self.controller.stop()

    async def test_fan_manual(self) -> None:
        self.assertTrue(
            self.controller.fan_manual_control,
            "Simulated drive expected to start in manual mode",
        )
        await self.controller.fan_manual_control(False)
        self.assertFalse(
            await self.controller.get_fan_manual_control(),
            "set_fan_manual_control should change state (to False)",
        )
        await self.controller.fan_manual_control(True)
        self.assertTrue(
            await self.controller.get_fan_manual_control(),
            "set_fan_manual_control should change state (to True)",
        )

    async def test_start_fan(self) -> None:
        self.assertEqual(
            0.0,
            await self.controller.get_fan_frequency(),
            "Simulated drive expected to start with fan at zero",
        )
        await self.controller.start_fan()
        self.assertEqual(
            self.controller.default_fan_frequency,
            await self.controller.get_fan_frequency(),
            "start_fan should change fan frequency to default value",
        )

    async def test_fan_stop_fan(self) -> None:
        await self.controller.start_fan()
        self.assertNotEqual(
            0.0,
            await self.controller.get_fan_frequency(),
            "start_fan should have started the fan",
        )
        await self.controller.stop_fan()
        self.assertEqual(
            0.0,
            await self.controller.get_fan_frequency(),
            "stop_fan should change fan frequency to 0.0",
        )

    async def test_set_fan_frequency(self) -> None:
        await self.controller.start_fan()
        self.assertNotEqual(
            0.0,
            await self.controller.get_fan_frequency(),
            "start_fan should have started the fan",
        )
        target_frequency = self.controller.default_fan_frequency / 2
        await self.controller.set_fan_frequency(target_frequency)
        self.assertAlmostEqual(
            target_frequency,
            await self.controller.get_fan_frequency(),
            places=1,
            msg="set_fan_frequency should change fan frequency to 50.0",
        )

    async def test_fault_recover(self) -> None:
        r = await self.controller.vfd_fault_reset()
        self.assertIsNone(r)  # Yay I guess

    async def test_last8faults(self) -> None:
        last8 = await self.controller.last8faults()
        self.assertEqual(len(last8), 8, "last8faults should return 8 elements")
        for i, s in last8:
            self.assertIsInstance(i, int)
            self.assertIsInstance(s, str)
            self.assertEqual(i, 22)
            self.assertTrue("undervolt" in s)

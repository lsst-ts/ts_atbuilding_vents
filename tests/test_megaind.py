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

from lsst.ts.vent.controller import Controller
from lsst.ts.vent.controller.ATBuilding import VentGateState


class TestLouvres(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.controller = Controller(simulate=True)
        await self.controller.connect()

    async def asyncTearDown(self):
        await self.controller.stop()

    async def test_vent_open(self):
        self.controller.vent_open(0)
        self.assertEqual(self.controller.vent_state(0), VentGateState.OPENED)

    async def test_vent_close(self):
        self.controller.vent_close(0)
        self.assertEqual(self.controller.vent_state(0), VentGateState.CLOSED)

    async def test_vent_partiallyopen(self):
        self.controller.simulator.set_bits((0, 0, 0, 0))
        self.assertEqual(self.controller.vent_state(0), VentGateState.PARTIALLY_OPEN)

    @unittest.expectedFailure
    async def test_vent_invalidstate(self):
        # There currently is no FAULT attribute in the VentGateState enum
        self.controller.simulator.set_bits((1, 1, 1, 1))
        self.assertEqual(self.controller.vent_state(0), VentGateState.FAULT)

    def test_vent_invalidvent(self):
        with self.assertRaises(ValueError):
            self.controller.vent_open(1000000)
        with self.assertRaises(ValueError):
            self.controller.vent_close(1000000)
        with self.assertRaises(ValueError):
            self.controller.vent_state(1000000)

    async def test_non_configured_vent(self):
        with self.assertRaises(ValueError):
            self.controller.vent_open(1)
        with self.assertRaises(ValueError):
            self.controller.vent_close(1)
        with self.assertRaises(ValueError):
            self.controller.vent_state(1)

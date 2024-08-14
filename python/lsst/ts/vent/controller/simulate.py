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

import os

from pymodbus.server import ModbusSimulatorServer

from .config import Config


class DomeVentsSimulator:
    def __init__(self, config: Config):
        self.input_bits = [0, 0, 0, 0]
        self.cfg = config

        self.modbus_simulator = ModbusSimulatorServer(
            modbus_server="server",
            modbus_device="device",
            http_host="localhost",
            http_port=25074,
            json_file=os.path.dirname(__file__) + "/simulator_setup.json",
        )

    async def start(self):
        await self.modbus_simulator.run_forever(only_start=True)

    async def stop(self):
        await self.modbus_simulator.stop()

    def getOptoCh(self, stack: int, channel: int) -> int:
        """Simulates the behavior of megaind.getOptoCh, as if connected
        to dome vents configured as described in config.py.

        Returns
        -------
        The state of the digital input channel, 1 (active) or 0 (inactive)

        Raises
        ------
        AssertionError
            If an invalid channel (outside the range 1 to 4) is requested
            or the stack index does not match the configured value.
        """

        channel -= 1  # Channels are 1-indexed

        assert stack == self.cfg.megaind_stack
        assert 0 <= channel <= 3
        return self.input_bits[channel]

    def setOd(self, stack: int, channel: int, val: int) -> None:
        """Simulates the behavior of megaind.setOd, as if connected
        to dome vents configured as described in config.py.

        Raises
        ------
        AssertionError
            If an invalid channel (outside the range 1 to 4) is requested,
            or the stack does not match the configured value, or the
            specified `val` is not zero or one.
        """

        channel -= 1  # Channels are 1-indexed

        assert stack == self.cfg.megaind_stack
        assert 0 <= channel <= 3
        assert val == 0 or val == 1
        vent_number = [i for i in range(4) if self.cfg.vent_signal_ch[i] - 1 == channel]
        assert len(vent_number) <= 1
        if len(vent_number) == 1:
            vent_number = vent_number[0]
            op = val
            cl = 0 if val else 1
            self.input_bits[self.cfg.vent_open_limit_ch[vent_number] - 1] = op
            self.input_bits[self.cfg.vent_close_limit_ch[vent_number] - 1] = cl

    def set_bits(self, input_bits: tuple[int]) -> None:
        """Sets the state of the simulated daughterboard.

        Raises
        ------
        AssertionError
            If input_bits does not have length 4.
        """
        assert len(input_bits) == 4
        self.input_bits = input_bits

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
import random

from pymodbus.server import ModbusSimulatorServer

from .config import Config


class DomeVentsSimulator:
    def __init__(self, config: Config):
        self.input_bits = [0] * 16
        self.cfg = config

        self.http_port = random.randint(1024, 65535)
        self.modbus_simulator = ModbusSimulatorServer(
            modbus_server="server",
            modbus_device="device",
            http_host="localhost",
            http_port=self.http_port,
            json_file=os.path.dirname(__file__) + "/simulator_setup.json",
        )

    async def start(self) -> None:
        await self.modbus_simulator.run_forever(only_start=True)

    async def stop(self) -> None:
        await self.modbus_simulator.stop()

    def read_channel(
        self, bus_number: int, stack_number: int, channel_number: int
    ) -> int:
        """Simulates the behavior of seequent.read_channel, as if connected
        to dome vents configured as described in config.py.

        Parameters
        ----------
        bus_number : int
            I2C hardware bus number. The hardware is addressable by the
            device /dev/i2c-{bus_number}.

        stack_number : int
            The hardware stack number for the I/O card.

        channel_number : int
            The I/O channel number to read.

        Returns
        -------
        The state of the digital input channel, 1 (active) or 0 (inactive)

        Raises
        ------
        AssertionError
            If an invalid channel (outside the range 1 to 16) is requested
            or the stack index does not match the configured value.
        """

        channel_number -= 1  # Channels are 1-indexed

        assert bus_number == self.cfg.sixteen_bus
        assert stack_number == self.cfg.sixteen_stack
        assert 0 <= channel_number <= 15
        return self.input_bits[channel_number]

    def write_channel(
        self, bus_number: int, stack_number: int, channel_number: int, value: int
    ) -> None:
        """Simulates the behavior of sequent.write_channel, as if connected
        to dome vents configured as described in config.py.

        Parameters
        ----------
        bus_number : int
            The I2C bus number of the device

        stack_number : int
            The hardware stack number for the I/O card.

        channel_number : int
            The I/O channel number to write.

        value : int
            The value to send to the I/O output, 1 for high or 0 for low.

        Raises
        ------
        AssertionError
            If an invalid channel (outside the range 1 to 4) is requested,
            or the stack does not match the configured value, or the
            specified `val` is not zero or one.
        """

        channel_number -= 1  # Channels are 1-indexed

        assert bus_number == self.cfg.megaind_bus
        assert stack_number == self.cfg.megaind_stack
        assert 0 <= channel_number <= 15
        assert value == 0 or value == 1
        vent_number_array = [
            i for i in range(4) if self.cfg.vent_signal_ch[i] - 1 == channel_number
        ]
        assert len(vent_number_array) <= 1
        if len(vent_number_array) == 1:
            vent_number = vent_number_array[0]
            op = value
            cl = 0 if value else 1
            self.input_bits[self.cfg.vent_open_limit_ch[vent_number] - 1] = op
            self.input_bits[self.cfg.vent_close_limit_ch[vent_number] - 1] = cl

    def set_bits(self, input_bits: tuple[int]) -> None:
        """Sets the state of the simulated daughterboard.

        Raises
        ------
        AssertionError
            If input_bits does not have length 16.
        """
        assert len(input_bits) == 16
        self.input_bits = list(input_bits)

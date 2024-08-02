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

import logging
from enum import IntEnum

import megaind
import pymodbus.client

from .config import Config
from . import vfd

__all__ = ["Controller"]


class VentGateState(IntEnum):
    CLOSED = 0
    PARTIALLY_OPEN = 1
    OPEN = 2
    FAULT = -1


class Controller:
    """A controller that commands the components associated with the AT dome
    vents and fans. The code in this class is meant to run on the Raspberry Pi
    described in
    https://confluence.lsstcorp.org/display/~fritzm/Auxtel+Vent+Gate+Automation.
    """

    def __init__(self, config: Config = Config()):
        self.cfg = config
        self.default_fan_frequency = self.cfg.max_freq
        self.log = logging.getLogger(type(self).__name__)

    async def connect(self) -> None:
        """Connects to the VFD via modbus.

        Raises
        ------ 
        ModbusException
            If the VFD is not available.
        """
        self.vfd_client = pymodbus.client.AsyncModbusTcpClient(self.cfg.hostname, port=self.cfg.port)
        await self.vfd_client.connect()

    async def get_fan_manual_control(self) -> bool:
        """Returns the VFD setting for manual or automatic (modbus) control.

        Returns
        -------
        bool
            True if the VFD is configured to be controlled externally, or False if
            the VFD is configured for automatic control.

        Raises
        ------
        ValueError
            If the VFD settings don't match either profile.

        ModbusException
            If a communications error occurs.
        """

        self.log.debug("get vfd_manual_control")
        settings = tuple(
            [
                (await self.vfd_client.read_holding_registers(slave=self.cfg.slave, address=addr)).registers[
                    0
                ]
                for addr in vfd.CFG_REGISTERS
            ]
        )
        if settings == vfd.MANUAL:
            return True
        if settings == vfd.AUTO:
            return False
        self.log.warning(f"Invalid settings in VFD: {settings=}")
        raise ValueError("Invalid settings in VFD")

    async def fan_manual_control(self, manual: bool) -> None:
        """Sets the VFD for manual or automatic (modbus) control.

        Parameters
        ----------
        manual : bool
            Whether the VFD should be controlled manually (True) or 
            by modbus (False).

        Raises
        ------
        ModbusException
            If a communications error occurs.
        """

        self.log.debug("set vfd_manual_control")
        settings = vfd.MANUAL if manual else vfd.AUTO
        for address, value in zip(vfd.CFG_REGISTERS, settings):
            await self.vfd_client.write_register(slave=self.cfg.slave, address=address, value=value)

    async def start_fan(self):
        """Starts the dome exhaust fan

        Raises
        ------
        ModbusException
            If a communications error occurs.
        """
        self.log.debug("start_fan()")
        await self.set_fan_frequency(self.default_fan_frequency)

    async def stop_fan(self):
        """Stops the dome exhaust fan

        Raises
        ------
        ModbusException
            If a communications error occurs.
        """
        self.log.debug("stop_fan()")
        await self.set_fan_frequency(0.0)

    async def get_fan_frequency(self) -> float:
        """Returns the target frequency configured in the drive.

        Raises
        ------
        ModbusException
            If a communications error occurs.
        """

        self.log.debug("get fan_frequency")
        cmd = (
            await self.vfd_client.read_holding_registers(
                slave=self.cfg.slave, address=vfd.Registers.CMD_REGISTER
            )
        ).registers[0]
        if cmd == 0:
            return 0.0

        lfr = (
            await self.vfd_client.read_holding_registers(
                slave=self.cfg.slave, address=vfd.Registers.LFR_REGISTER
            )
        ).registers[0]
        return 0.1 * lfr

    async def set_fan_frequency(self, frequency: float) -> None:
        """Sets the target frequency for the dome exhaust fan. The frequency
        must be between zero and MAX_FREQ.

        Parameters
        ----------
        frequency : float
            The desired VFD frequency in Hz.

        Raises
        ------
        ValueError
            If the frequency is not between zero and MAX_FREQ.

        ModbusException
            If a communications error occurs.
        """
        self.log.debug("set fan_frequency")
        if not 0 <= frequency <= self.cfg.max_freq:
            raise ValueError(f"Frequency must be between 0 and {self.cfg.max_freq}")

        settings = {
            vfd.Registers.CMD_REGISTER: 0 if frequency == 0.0 else 1,
            vfd.Registers.LFR_REGISTER: round(frequency * 10),
        }
        for address, value in settings.items():
            await self.vfd_client.write_register(slave=self.cfg.slave, address=address, value=value)

    async def vfd_fault_reset(self) -> None:
        """Resets a fault condition on the drive so that it will operate again.

        Raises
        ------
        ModbusException
            If a communications error occurs.
        """

        for address, value in vfd.FAULT_RESET_SEQUENCE:
            await self.vfd_client.write_register(slave=self.cfg.slave, address=address, value=value)

    async def last8faults(self) -> list[tuple[int, str]]:
        """Returns the last eight fault conditions recorded by the drive.

        Returns
        -------
        list[tuple[int, str]]
            A list containing 8 tuples each with length 2. The first element in the
            tuple is an integer fault code, and the second is a human-readable
            description of the fault code.

        Raises
        ------
        ModbusException
            If a communications error occurs.
        """

        self.log.debug("last8faults")
        rvals = await self.vfd_client.read_holding_registers(
            slave=1, address=vfd.Registers.FAULT_REGISTER, count=8
        )
        return [(r, vfd.FAULTS[r]) for r in rvals.registers]

    def vent_open(self, vent_number: int) -> None:
        """Opens the specified vent.

        Parameters
        ----------
        vent_number : int
            The choice of vent to open, from 0 to 3.

        Raises
        ------
        ValueError
            If vent_number is invalid.

        RuntimeError
            If a communications error occurs.
        """

        self.log.debug(f"vent_open({vent_number})")
        if not 0 <= vent_number <= 3:
            raise ValueError(f"Invalid {vent_number=} should be between 0 and 3")
        if self.cfg.vent_signal_ch[vent_number] == -1:
            raise ValueError(f"Vent {vent_number=} is not configured.")
        megaind.setOd(self.cfg.megaind_stack, self.cfg.vent_signal_ch[vent_number], 1)

    def vent_close(self, vent_number: int) -> None:
        """Closes the specified vent.

        Parameters
        ----------
        vent_number the choice of vent to open, from 0 to 3

        Raises
        ------
        ValueError
            If vent_number is invalid.

        RuntimeError
            If a communications error occurs.
        """

        self.log.debug(f"vent_close({vent_number})")
        if not 0 <= vent_number <= 3:
            raise ValueError(f"Invalid {vent_number=} should be between 0 and 3")
        if self.cfg.vent_signal_ch[vent_number] == -1:
            raise ValueError(f"Vent {vent_number=} is not configured.")
        megaind.setOd(self.cfg.megaind_stack, self.cfg.vent_signal_ch[vent_number], 0)

    def vent_state(self, vent_number: int) -> VentGateState:
        """Returns the state of the specified vent.

        Parameters
        ----------
        vent_number : int
            The choice of vent to open, from 0 to 3.

        Raises
        ------
        ValueError
            If vent_number is invalid.

        RuntimeError
            If a communications error occurs.
        """

        self.log.debug(f"vent_state({vent_number})")
        if not 0 <= vent_number <= 3:
            raise ValueError(f"Invalid {vent_number=} should be between 0 and 3")

        if self.cfg.vent_open_limit_ch[vent_number] == -1 or self.cfg.vent_close_limit_ch[vent_number] == -1:
            raise ValueError(f"Vent {vent_number=} is not configured.")

        op_state = megaind.getOptoCh(self.cfg.megaind_stack, self.cfg.vent_open_limit_ch[vent_number])
        cl_state = megaind.getOptoCh(self.cfg.megaind_stack, self.cfg.vent_close_limit_ch[vent_number])

        match op_state, cl_state:
            case 1, 0:
                return VentGateState.OPEN
            case 0, 0:
                return VentGateState.PARTIALLY_OPEN
            case 0, 1:
                return VentGateState.CLOSED
            case _:
                return VentGateState.FAULT

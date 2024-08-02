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
from enum import IntEnum
import logging
import os
import pymodbus.client

import megaind

from . import config as cfg
from .vfd import *

__all__ = ["Controller"]
logger = logging.getLogger(__name__)


class VentGateState(IntEnum):
    CLOSED = 0
    """
    The vent is closed
    """

    PARTIALLY_OPEN = 1
    """
    The vent is neither open nor closed
    """

    OPEN = 2
    """
    The vent is open
    """

    FAULT = -1
    """
    The vent is both open and closed
    """


class Controller:
    """A controller that commands the components associated with the AT dome vents and fans.
    The code in this class is meant to run on the Raspberry Pi described in
    https://confluence.lsstcorp.org/display/~fritzm/Auxtel+Vent+Gate+Automation
    """

    def __init__(self):
        """Constructor."""
        logger.debug("__init__")

        vfd_hostname = cfg.VFD_HOSTNAME
        if "VFD_HOSTNAME" in os.environ:
            vfd_hostname = os.environ["VFD_HOSTNAME"]

        vfd_port = cfg.VFD_PORT
        if "VFD_PORT" in os.environ:
            vfd_port = int(os.environ["VFD_PORT"])

        self.vfd_client = pymodbus.client.AsyncModbusTcpClient(vfd_hostname, port=vfd_port)
        self.vfd_slave = cfg.VFD_SLAVE
        self.default_fan_frequency = cfg.VFD_MAX_FREQ


    async def connect(self) -> None:
        """Connects to the VFD via modbus.

        Raises
        ======
        ModbusException if the VFD is not available.
        """
        await self.vfd_client.connect()


    async def get_vfd_manual_control(self) -> bool:
        """Returns the VFD setting for manual or automatic (modbus) control.

        Returns
        =======
        True if the VFD is configured to be controlled externally, or False if the VFD is configured
        for automatic control

        Raises
        ======
        ValueError if the VFD settings don't match either profile

        ModbusException if a communications error occurs
        """

        logger.debug("get vfd_manual_control")
        settings = tuple(
            [
                (await self.vfd_client.read_holding_registers(
                    slave=self.vfd_slave, address=addr
                )).registers[0]
                for addr in CFG_REGISTERS
            ]
        )
        if settings == VFD_MANUAL:
            return True
        if settings == VFD_AUTO:
            return False
        logger.warning(f"Invalid settings in VFD: {settings=}")
        raise ValueError("Invalid settings in VFD")

    async def vfd_manual_control(self, manual: bool) -> None:
        """Sets the VFD for manual or automatic (modbus) control.

        Parameters
        ==========
        manual whether the VFD should be controlled manually (True) or by modbus (False)

        Raises
        ======
        ModbusException if a communications error occurs
        """

        logger.debug("set vfd_manual_control")
        settings = VFD_MANUAL if manual else VFD_AUTO
        for address, value in zip(CFG_REGISTERS, settings):
            await self.vfd_client.write_register(
                slave=self.vfd_slave, address=address, value=value
            )

    async def start_fan(self):
        """Starts the dome exhaust fan

        Raises
        ======
        ModbusException if a communications error occurs
        """
        logger.debug("start_fan()")
        await self.set_fan_frequency(self.default_fan_frequency)

    async def stop_fan(self):
        """Stops the dome exhaust fan

        Raises
        ======
        ModbusException if a communications error occurs
        """
        logger.debug("stop_fan()")
        await self.set_fan_frequency(0.0)

    async def get_fan_frequency(self) -> float:
        """Returns the target frequency configured in the VFD.

        Raises
        ======
        ModbusException if a communications error occurs
        """

        logger.debug("get fan_frequency")
        cmd = (await self.vfd_client.read_holding_registers(
            slave=self.vfd_slave, address=Registers.CMD_REGISTER
        )).registers[0]
        if cmd == 0:
            return 0.0

        lfr = (await self.vfd_client.read_holding_registers(
            slave=self.vfd_slave, address=Registers.LFR_REGISTER
        )).registers[0]
        return 0.1 * lfr

    async def set_fan_frequency(self, frequency: float) -> None:
        """Sets the target frequency for the dome exhaust fan. The frequency must be between
        zero and VFD_MAX_FREQ.

        Parameters
        ==========
        frequency the desired VFD frequency in Hz

        Raises
        ======
        ValueError if the frequency is not between zero and VFD_MAX_FREQ

        ModbusException if a communications error occurs
        """
        logger.debug("set fan_frequency")
        if not 0 <= frequency <= cfg.VFD_MAX_FREQ:
            raise ValueError(f"Frequency must be between 0 and {cfg.VFD_MAX_FREQ}")

        settings = {
            Registers.CMD_REGISTER: 0 if frequency == 0.0 else 1,
            Registers.LFR_REGISTER: round(frequency * 10),
        }
        for address, value in settings.items():
            await self.vfd_client.write_register(
                slave=self.vfd_slave, address=address, value=value
            )

    async def vfd_fault_reset(self) -> None:
        """Resets a fault condition on the VFD so that it will operate again.

        Raises
        ======
        ModbusException if a communications error occurs
        """

        for address, value in FAULT_RESET_SEQUENCE:
            await self.vfd_client.write_register(
                slave=self.vfd_slave, address=address, value=value
            )

    async def last8faults(self) -> list[tuple[int, str]]:
        """Returns the last eight fault conditions recorded by the VFD

        Returns
        =======
        A list containing 8 tuples each with length 2. The first element in the tuple is
        an integer fault code, and the second is a human-readable description of the fault code.

        Raises
        ======
        ModbusException if a communications error occurs
        """

        logger.debug("last8faults")
        rvals = await self.vfd_client.read_holding_registers(
            slave=1, address=Registers.FAULT_REGISTER, count=8
        )
        return [
            (r, VFD_FAULTS[r]) for r in rvals.registers
        ]

    def vent_open(self, vent_number: int) -> None:
        """Opens the specified vent.

        Parameters
        ==========
        vent_number the choice of vent to open, from 0 to 3

        Raises
        ======
        ValueError if vent_number is invalid

        RuntimeError if a communications error occurs
        """

        logger.debug(f"vent_open({vent_number})")
        if not 0 <= vent_number <= 3:
            raise ValueError(f"Invalid {vent_number=} should be between 0 and 3")
        if cfg.VENT_SIGNAL_CH[vent_number] == -1:
            raise ValueError(f"Vent {vent_number=} is not configured.")
        megaind.set0_10Out(cfg.MEGAIND_STACK, cfg.VENT_SIGNAL_CH[vent_number], 10.0)

    def vent_close(self, vent_number: int) -> None:
        """Closes the specified vent.

        Parameters
        ==========
        vent_number the choice of vent to open, from 0 to 3

        Raises
        ======
        ValueError if vent_number is invalid

        RuntimeError if a communications error occurs
        """

        logger.debug(f"vent_close({vent_number})")
        if not 0 <= vent_number <= 3:
            raise ValueError(f"Invalid {vent_number=} should be between 0 and 3")
        if cfg.VENT_SIGNAL_CH[vent_number] == -1:
            raise ValueError(f"Vent {vent_number=} is not configured.")
        megaind.set0_10Out(cfg.MEGAIND_STACK, cfg.VENT_SIGNAL_CH[vent_number], 0.0)

    def vent_state(self, vent_number: int) -> VentGateState:
        """Returns the state of the specified vent.

        Parameters
        ==========
        vent_number the choice of vent to open, from 0 to 3


        Raises
        ======
        ValueError if vent_number is invalid

        RuntimeError if a communications error occurs
        """

        logger.debug(f"vent_state({vent_number})")
        if not 0 <= vent_number <= 3:
            raise ValueError(f"Invalid {vent_number=} should be between 0 and 3")

        if cfg.VENT_OPEN_LIMIT_CH[vent_no] == -1 or cfg.VENT_CLOSE_LIMIT_CH[vent_no] == -1:
            raise ValueError(f"Vent {vent_number=} is not configured.")

        op_state = megaind.getOptoCh(cfg.MEGAIND_STACK, cfg.VENT_OPEN_LIMIT_CH[vent_no])
        cl_state = megaind.getOptoCh(
            cfg.MEGAIND_STACK, cfg.VENT_CLOSE_LIMIT_CH[vent_no]
        )

        match op_state, cl_state:
            case 1, 0:
                return VentGateState.OPEN
            case 0, 0:
                return VentGateState.PARTIALLY_OPEN
            case 0, 1:
                return VentGateState.CLOSED
            case _:
                return VentGateState.FAULT

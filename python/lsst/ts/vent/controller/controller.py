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

try:
    import megaind

    MEGAIND_AVAILABLE = True
except ImportError:
    MEGAIND_AVAILABLE = False
import pymodbus.client

from . import vf_drive
from .config import Config
from .simulate import DomeVentsSimulator

__all__ = ["Controller"]


class VentGateState(IntEnum):
    CLOSED = 0
    PARTIALLY_OPEN = 1
    OPEN = 2
    FAULT = -1


class FanDriveState(IntEnum):
    STOPPED = 0
    OPERATING = 1
    FAULT = 2


class Controller:
    """A controller that commands the components associated with the AT dome
    vents and fans. The code in this class is meant to run on the Raspberry Pi
    described in
    https://confluence.lsstcorp.org/display/~fritzm/Auxtel+Vent+Gate+Automation.
    """

    def __init__(self, config: Config = Config(), simulate: bool = False):
        self.cfg = config
        self.default_fan_frequency = self.cfg.max_freq
        self.log = logging.getLogger(type(self).__name__)
        self.simulate = simulate
        self.simulator = DomeVentsSimulator(self.cfg) if simulate else None

    async def connect(self) -> None:
        """Connects to the variable frequency drive via modbus.

        Raises
        ------
        ModbusException
            If the variable frequency drive is not available.
        """
        if self.simulate:
            await self.simulator.start()

        self.vfd_client = pymodbus.client.AsyncModbusTcpClient(
            self.cfg.hostname, port=self.cfg.port
        )
        await self.vfd_client.connect()

    async def stop(self) -> None:
        """Disconnects from the variable frequency drive, and stops
        the simulator if simulating.
        """
        if self.simulate:
            await self.simulator.stop()

        self.vfd_client.close()

    async def get_fan_manual_control(self) -> bool:
        """Returns the variable frequency drive setting for manual
        or automatic (modbus) control.

        Returns
        -------
        bool
            True if the drive is configured to be controlled externally, or
            False if the drive is configured for automatic control.

        Raises
        ------
        ValueError
            If the drive settings don't match either profile.

        ModbusException
            If a communications error occurs.
        """

        self.log.debug("get fan_manual_control")
        settings = tuple(
            [
                (
                    await self.vfd_client.read_holding_registers(
                        slave=self.cfg.slave, address=addr
                    )
                ).registers[0]
                for addr in vf_drive.CFG_REGISTERS
            ]
        )
        if settings == vf_drive.MANUAL:
            return True
        if settings == vf_drive.AUTO:
            return False
        self.log.warning(f"Invalid settings in variable frequency drive: {settings=}")
        raise ValueError("Invalid settings in variable frequency drive")

    async def fan_manual_control(self, manual: bool) -> None:
        """Sets the variable frequency drive for manual or automatic (modbus)
        control of the fan.

        Parameters
        ----------
        manual : bool
            Whether the drive should be controlled manually (True) or
            by modbus (False).

        Raises
        ------
        ModbusException
            If a communications error occurs.
        """

        self.log.debug("set vfd_manual_control")
        settings = vf_drive.MANUAL if manual else vf_drive.AUTO
        for address, value in zip(vf_drive.CFG_REGISTERS, settings):
            await self.vfd_client.write_register(
                slave=self.cfg.slave, address=address, value=value
            )

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
                slave=self.cfg.slave, address=vf_drive.Registers.CMD_REGISTER
            )
        ).registers[0]
        if cmd == 0:
            return 0.0

        lfr = (
            await self.vfd_client.read_holding_registers(
                slave=self.cfg.slave, address=vf_drive.Registers.LFR_REGISTER
            )
        ).registers[0]
        return 0.1 * lfr

    async def set_fan_frequency(self, frequency: float) -> None:
        """Sets the target frequency for the dome exhaust fan. The frequency
        must be between zero and MAX_FREQ.

        Parameters
        ----------
        frequency : float
            The desired fan frequency in Hz.

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
            vf_drive.Registers.CMD_REGISTER: 0 if frequency == 0.0 else 1,
            vf_drive.Registers.LFR_REGISTER: round(frequency * 10),
        }
        for address, value in settings.items():
            await self.vfd_client.write_register(
                slave=self.cfg.slave, address=address, value=value
            )

    async def vfd_fault_reset(self) -> None:
        """Resets a fault condition on the drive so that it will operate again.

        Raises
        ------
        ModbusException
            If a communications error occurs.
        """

        for address, value in vf_drive.FAULT_RESET_SEQUENCE:
            await self.vfd_client.write_register(
                slave=self.cfg.slave, address=address, value=value
            )

    async def get_drive_state(self) -> FanDriveState:
        """Returns the current fan drive state based on the contents
        of the IPAE register.

        Raises
        ------
        ModbusException
            If a communications error occurs.
        """

        ipae = (
            await self.vfd_client.read_holding_registers(
                slave=self.cfg.slave, address=vf_drive.Registers.IPAE_REGISTER
            )
        ).registers[0]

        if ipae in (0, 1, 2, 3, 5):
            return FanDriveState.STOPPED
        if ipae == 4:
            return FanDriveState.OPERATING
        return FanDriveState.FAULT

    async def last8faults(self) -> list[tuple[int, str]]:
        """Returns the last eight fault conditions recorded by the drive.

        Returns
        -------
        list[tuple[int, str]]
            A list containing 8 tuples each with length 2. The first element in
            the tuple is an integer fault code, and the second is a
            human-readable description of the fault code.

        Raises
        ------
        ModbusException
            If a communications error occurs.
        """

        self.log.debug("last8faults")
        rvals = await self.vfd_client.read_holding_registers(
            slave=1, address=vf_drive.Registers.FAULT_REGISTER, count=8
        )
        return [(r, vf_drive.FAULTS[r]) for r in rvals.registers]

    def vent_open(self, vent_number: int) -> None:
        """Opens the specified vent.

        Parameters
        ----------
        vent_number : int
            The choice of vent to open, from 0 to 3.

        Raises
        ------
        ModuleNotFoundError
            If the megaind module has not been installed, in which case the
            daughterboard cannot be controlled.

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
        self.setOd(self.cfg.megaind_stack, self.cfg.vent_signal_ch[vent_number], 1)

    def vent_close(self, vent_number: int) -> None:
        """Closes the specified vent.

        Parameters
        ----------
        vent_number : int
            the choice of vent to open, from 0 to 3

        Raises
        ------
        ModuleNotFoundError
            If the megaind module has not been installed, in which case the
            daughterboard cannot be controlled.

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
        self.setOd(self.cfg.megaind_stack, self.cfg.vent_signal_ch[vent_number], 0)

    def vent_state(self, vent_number: int) -> VentGateState:
        """Returns the state of the specified vent.

        Parameters
        ----------
        vent_number : int
            The choice of vent to open, from 0 to 3.

        Raises
        ------
        ModuleNotFoundError
            If the megaind module has not been installed, in which case the
            daughterboard cannot be controlled.

        ValueError
            If vent_number is invalid.

        RuntimeError
            If a communications error occurs.
        """

        self.log.debug(f"vent_state({vent_number})")
        if not 0 <= vent_number <= 3:
            raise ValueError(f"Invalid {vent_number=} should be between 0 and 3")

        if (
            self.cfg.vent_open_limit_ch[vent_number] == -1
            or self.cfg.vent_close_limit_ch[vent_number] == -1
        ):
            raise ValueError(f"Vent {vent_number=} is not configured.")

        op_state = self.getOptoCh(
            self.cfg.megaind_stack, self.cfg.vent_open_limit_ch[vent_number]
        )
        cl_state = self.getOptoCh(
            self.cfg.megaind_stack, self.cfg.vent_close_limit_ch[vent_number]
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

    def getOptoCh(self, *args, **kwargs) -> int:
        """Calls megaind.getOptoCh or a simulated getOptoCh depending
        whether the class was instantiated with simulate = True.

        Raises
        ------
        ModuleNotFoundError
            If the megaind module has not been installed, in which case the
            daughterboard cannot be controlled.
        """

        if self.simulate:
            return self.simulator.getOptoCh(*args, **kwargs)
        else:
            if not MEGAIND_AVAILABLE:
                raise ModuleNotFoundError("The megaind module is not available.")
            return megaind.getOptoCh(*args, **kwargs)

    def setOd(self, *args, **kwargs) -> None:
        """Calls megaind.setOd or a simulated setOd depending
        whether the class was instantiated with simulate = True.

        Raises
        ------
        ModuleNotFoundError
            If the megaind module has not been installed, in which case the
            daughterboard cannot be controlled.
        """

        if self.simulate:
            self.simulator.setOd(*args, **kwargs)
        else:
            if not MEGAIND_AVAILABLE:
                raise ModuleNotFoundError("The megaind module is not available.")
            megaind.setOd(*args, **kwargs)

# This file is part of ts_atbuilding_vents.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import logging
import typing

import backoff
from lsst.ts.xml.enums.ATBuilding import FanDriveState, VentGateState
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException

from . import sequent, vf_drive
from .config import Config
from .dome_vents_simulator import SIMULATOR_MODBUS_PORT, DomeVentsSimulator

__all__ = ["Controller"]


class Controller:
    """A controller that commands the components associated with the AT dome
    vents and fans. The code in this class is meant to run on the Raspberry Pi
    described in
    https://confluence.lsstcorp.org/display/~fritzm/Auxtel+Vent+Gate+Automation.
    """

    def __init__(self, config: Config | None = None, simulate: bool = False):
        self.config = config if config is not None else Config()
        self.default_fan_frequency = self.config.max_freq
        self.log = logging.getLogger(type(self).__name__)
        self.simulator = DomeVentsSimulator(self.config) if simulate else None
        self.vfd_client: None | AsyncModbusTcpClient = None

        if simulate:
            # The simulated drive always listens on localhost at a fixed port,
            # so point the configuration at it rather than making every caller
            # remember to do so.
            self.config.hostname = "localhost"
            self.config.port = SIMULATOR_MODBUS_PORT

    @property
    def connected(self) -> bool:
        """Whether there is a live modbus connection to the variable
        frequency drive.

        This reflects the actual state of the socket, so it becomes False if
        the drive drops off the network and True again once pymodbus has
        reconnected.
        """
        return self.vfd_client is not None and self.vfd_client.connected

    def _log_connect_retry(self, details: typing.Mapping[str, typing.Any]) -> None:
        """Logs a failed attempt to connect to the variable frequency drive."""
        self.log.warning(
            f"Failed to connect to the variable frequency drive at "
            f"{self.config.hostname}:{self.config.port} after "
            f"{details['tries']} attempt(s). "
            f"Retrying in {details['wait']:.1f} seconds."
        )

    async def connect(self) -> None:
        """Connects to the variable frequency drive via modbus.

        The initial connection is retried with exponential backoff for up to
        ``config.connect_max_time`` seconds, so that the controller can start
        before the drive is powered up. Once a connection has been
        established, pymodbus reconnects automatically if it is lost, so the
        retry here applies only to the initial connection.

        Raises
        ------
        ConnectionException
            If the variable frequency drive cannot be reached before
            ``config.connect_max_time`` elapses.
        """
        if self.simulator is not None:
            await self.simulator.start()

        self.vfd_client = AsyncModbusTcpClient(
            self.config.hostname,
            port=self.config.port,
            timeout=self.config.modbus_timeout,
            retries=self.config.modbus_retries,
            reconnect_delay=self.config.reconnect_delay,
            reconnect_delay_max=self.config.reconnect_delay_max,
        )

        # pymodbus signals a failed connection by returning False rather than
        # raising, so retry on the return value. The decorator is applied here
        # rather than to a method so that it can read the retry limit from the
        # configuration.
        @backoff.on_predicate(
            backoff.expo,
            max_time=self.config.connect_max_time,
            jitter=backoff.full_jitter,
            on_backoff=self._log_connect_retry,
        )
        async def connect_once() -> bool:
            assert self.vfd_client is not None
            return await self.vfd_client.connect()

        if not await connect_once():
            raise ConnectionException(
                f"Could not connect to the variable frequency drive at "
                f"{self.config.hostname}:{self.config.port} after "
                f"{self.config.connect_max_time} seconds."
            )

        self.log.info(
            f"Connected to the variable frequency drive at "
            f"{self.config.hostname}:{self.config.port}."
        )

    async def stop(self) -> None:
        """Disconnects from the variable frequency drive, and stops
        the simulator if simulating.
        """
        if self.simulator is not None:
            await self.simulator.stop()

        if self.vfd_client is not None:
            self.vfd_client.close()

    async def read_registers(self, address: int, count: int = 1) -> list[int]:
        """Reads one or more holding registers from the variable frequency
        drive.

        pymodbus reports a modbus protocol error (an illegal address, say) by
        returning an ``ExceptionResponse`` rather than by raising, and that
        response has no ``registers`` attribute. Checking here means callers
        see a `ModbusException` rather than an `AttributeError`.

        Parameters
        ----------
        address : int
            The address of the first register to read.

        count : int
            The number of consecutive registers to read.

        Returns
        -------
        list[int]
            The contents of the registers read.

        Raises
        ------
        ModbusException
            If a communications error occurs, or the drive returns an error
            response.
        """
        assert self.vfd_client is not None
        response = await self.vfd_client.read_holding_registers(
            device_id=self.config.device_id, address=address, count=count
        )
        if response.isError():
            raise ModbusException(
                f"Error reading {count} register(s) at address {address} "
                f"from the variable frequency drive: {response}"
            )
        return response.registers

    async def write_register(self, address: int, value: int) -> None:
        """Writes a single holding register on the variable frequency drive.

        Parameters
        ----------
        address : int
            The address of the register to write.

        value : int
            The value to write to the register.

        Raises
        ------
        ModbusException
            If a communications error occurs, or the drive returns an error
            response.
        """
        assert self.vfd_client is not None
        response = await self.vfd_client.write_register(
            device_id=self.config.device_id, address=address, value=value
        )
        if response.isError():
            raise ModbusException(
                f"Error writing value {value} to register {address} "
                f"of the variable frequency drive: {response}"
            )

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
        AssertionError
            If the controller is not connected.

        ValueError
            If the drive settings don't match either profile.

        ModbusException
            If a communications error occurs.
        """

        self.log.debug("get fan_manual_control")
        assert self.connected
        assert self.vfd_client is not None
        settings = tuple(
            [
                (await self.read_registers(address=addr))[0]
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
        AssertionError
            If the controller is not connected.

        ModbusException
            If a communications error occurs.
        """

        self.log.debug("set vfd_manual_control")
        assert self.connected
        assert self.vfd_client is not None

        await self.set_fan_frequency(0.0)

        settings = vf_drive.MANUAL if manual else vf_drive.AUTO
        for address, value in zip(vf_drive.CFG_REGISTERS, settings):
            await self.write_register(address=address, value=value)

    async def start_fan(self) -> None:
        """Starts the dome exhaust fan

        Raises
        ------
        AssertionError
            If the controller is not connected.

        ModbusException
            If a communications error occurs.
        """
        self.log.debug("start_fan()")
        assert self.connected
        await self.set_fan_frequency(self.default_fan_frequency)

    async def stop_fan(self) -> None:
        """Stops the dome exhaust fan

        Raises
        ------
        AssertionError
            If the controller is not connected.

        ModbusException
            If a communications error occurs.
        """
        self.log.debug("stop_fan()")
        assert self.connected
        await self.set_fan_frequency(0.0)

    async def get_fan_frequency(self) -> float:
        """Returns the target frequency configured in the drive.

        Raises
        ------
        AssertionError
            If the controller is not connected.

        ModbusException
            If a communications error occurs.
        """

        self.log.debug("get fan_frequency")
        assert self.connected
        assert self.vfd_client is not None

        output_frequency = float(
            (await self.read_registers(address=vf_drive.Registers.RFR_REGISTER))[0]
        )
        output_frequency *= 0.1  # RFR register holds frequency in units of 0.1 Hz
        return output_frequency

    def get_max_frequency(self) -> float:
        """Returns the maximum allowed frequency.

        Calls to `set_fan_frequency` may not have an argument exceeding
        this value.
        """
        return self.config.max_freq

    async def set_fan_frequency(self, frequency: float) -> None:
        """Sets the target frequency for the dome exhaust fan. The frequency
        must be between zero and MAX_FREQ.

        Parameters
        ----------
        frequency : float
            The desired fan frequency in Hz.

        Raises
        ------
        AssertionError
            If the controller is not connected.

        ValueError
            If the frequency is not between zero and MAX_FREQ.

        ModbusException
            If a communications error occurs.
        """
        self.log.debug("set fan_frequency")
        assert self.connected
        assert self.vfd_client is not None
        if not 0 <= frequency <= self.config.max_freq:
            raise ValueError(f"Frequency must be between 0 and {self.config.max_freq}")

        settings = {
            vf_drive.Registers.CMD_REGISTER: 0 if frequency == 0.0 else 1,
            vf_drive.Registers.LFR_REGISTER: round(frequency * 10),
        }
        for address, value in settings.items():
            await self.write_register(address=address, value=value)

    async def vfd_fault_reset(self) -> None:
        """Resets a fault condition on the drive so that it will operate again.

        Raises
        ------
        AssertionError
            If the controller is not connected.

        ModbusException
            If a communications error occurs.
        """

        assert self.connected
        assert self.vfd_client is not None
        for address, value in vf_drive.FAULT_RESET_SEQUENCE:
            await self.write_register(address=address, value=value)

    async def get_drive_state(self) -> FanDriveState:
        """Returns the current fan drive state based on the contents
        of the HMIS register. This register may have a number of
        possible values, most of which should never be encountered
        in operation of the drive. We interpret this register as
        follows based on real-world observations of the drive

         * A value of 4 (Drive running), 5 (Drive accelerating), or
           6 (Drive decelerating) corresponds to
           FanDriveState.OPERATING
         * A value of 2 (Drive ready) corresponds to FanDriveState.STOPPED
         * All other values correspond to FanDriveState.FAULT

        Raises
        ------
        AssertionError
            If the controller is not connected.

        ModbusException
            If a communications error occurs.

        Returns
        -------
        `FanDriveState`
            The current fan drive state based on the contents of the
            ATV320 HMIS register.
        """

        assert self.connected
        assert self.vfd_client is not None
        hmis = (await self.read_registers(address=vf_drive.Registers.HMIS_REGISTER))[0]

        if hmis in (4, 5, 6):
            return FanDriveState.OPERATING
        if hmis == 2:
            return FanDriveState.STOPPED
        return FanDriveState.FAULT

    async def get_drive_voltage(self) -> float:
        """Returns a measurement from the fan motor drive's line voltage.

        Raises
        ------
        AssertionError
            If the controller is not connected.

        ModbusException
            If a communications error occurs.
        """

        self.log.debug("get drive_voltage")
        assert self.connected
        assert self.vfd_client is not None

        drive_voltage = float(
            (await self.read_registers(address=vf_drive.Registers.ULN_REGISTER))[0]
        )
        drive_voltage *= 0.1  # ULN register holds voltage in units of 0.1 V
        return drive_voltage

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
        AssertionError
            If the controller is not connected.

        ModbusException
            If a communications error occurs.
        """

        self.log.debug("last8faults")
        assert self.connected
        assert self.vfd_client is not None
        rvals = await self.read_registers(
            address=vf_drive.Registers.FAULT_REGISTER, count=8
        )
        return [
            (r, vf_drive.FAULTS.get(r, f"Unknown fault code {r}"))
            for r in reversed(rvals)
        ]

    def vent_open(self, vent_number: int) -> None:
        """Opens the specified vent.

        Parameters
        ----------
        vent_number : int
            The choice of vent to open, from 0 to 3.

        Raises
        ------
        AssertionError
            If the controller is not connected.

        ValueError
            If vent_number is invalid.

        RuntimeError
            If a communications error occurs.
        """

        self.log.debug(f"vent_open({vent_number})")
        assert self.connected
        if not 0 <= vent_number <= 3:
            raise ValueError(f"Invalid {vent_number=} should be between 0 and 3")
        if self.config.vent_signal_ch[vent_number] == -1:
            raise ValueError(f"Vent {vent_number=} is not configured.")
        self.write_channel(
            self.config.megaind_bus,
            self.config.megaind_stack,
            self.config.vent_signal_ch[vent_number],
            1,
        )

    def vent_close(self, vent_number: int) -> None:
        """Closes the specified vent.

        Parameters
        ----------
        vent_number : int
            the choice of vent to open, from 0 to 3

        Raises
        ------
        AssertionError
            If the controller is not connected.

        ValueError
            If vent_number is invalid.

        RuntimeError
            If a communications error occurs.
        """

        self.log.debug(f"vent_close({vent_number})")
        assert self.connected
        if not 0 <= vent_number <= 3:
            raise ValueError(f"Invalid {vent_number=} should be between 0 and 3")
        if self.config.vent_signal_ch[vent_number] == -1:
            raise ValueError(f"Vent {vent_number=} is not configured.")
        self.write_channel(
            self.config.megaind_bus,
            self.config.megaind_stack,
            self.config.vent_signal_ch[vent_number],
            0,
        )

    def vent_state(self, vent_number: int) -> VentGateState:
        """Returns the state of the specified vent.

        Parameters
        ----------
        vent_number : int
            The choice of vent to open, from 0 to 3.

        Raises
        ------
        AssertionError
            If the controller is not connected.

        ValueError
            If vent_number is invalid.

        RuntimeError
            If a communications error occurs.
        """

        self.log.debug(f"vent_state({vent_number})")
        assert self.connected
        if not 0 <= vent_number <= 3:
            raise ValueError(f"Invalid {vent_number=} should be between 0 and 3")

        if (
            self.config.vent_open_limit_ch[vent_number] == -1
            or self.config.vent_close_limit_ch[vent_number] == -1
        ):
            raise ValueError(f"Vent {vent_number=} is not configured.")

        op_state = self.read_channel(
            self.config.sixteen_bus,
            self.config.sixteen_stack,
            self.config.vent_open_limit_ch[vent_number],
        )
        cl_state = self.read_channel(
            self.config.sixteen_bus,
            self.config.sixteen_stack,
            self.config.vent_close_limit_ch[vent_number],
        )

        match op_state, cl_state:
            case 1, 0:
                return VentGateState.OPENED
            case 0, 0:
                return VentGateState.PARTIALLY_OPEN
            case 0, 1:
                return VentGateState.CLOSED
            case _:
                return VentGateState.FAULT

    def read_channel(
        self, bus_number: int, stack_number: int, channel_number: int
    ) -> int:
        """Calls hardware I/O or a simulated substitute depending
        whether the class was instantiated with simulate = True.

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
        int
            If the I/O input channel is high, returns 1, or,
            if the I/O input channel is low, returns 0.

        Raises
        ------
        AssertionError
            If the controller is not connected.
        """

        assert self.connected
        if self.simulator is not None:
            return self.simulator.read_channel(bus_number, stack_number, channel_number)
        else:
            return sequent.read_channel(bus_number, stack_number, channel_number)

    def write_channel(
        self, bus_number: int, stack_number: int, channel_number: int, value: int
    ) -> None:
        """Calls harware I/O or a simulated substitute depending
        whether the class was instantiated with simulate = True.

        Parameters
        ----------
        bus_number : int
            I2C hardware bus number. The hardware is addressable by the
            device /dev/i2c-{bus_number}.

        stack_number : int
            The hardware stack number for the I/O card.

        channel_number : int
            The I/O channel number to write.

        value : int
            The value to send to the I/O output, 1 for high or 0 for low.

        Raises
        ------
        AssertionError
            If the controller is not connected.
        """

        assert self.connected
        if self.simulator is not None:
            self.simulator.write_channel(
                bus_number, stack_number, channel_number, value
            )
        else:
            sequent.write_channel(bus_number, stack_number, channel_number, value)

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
import traceback
from typing import Final, Type, TypeVar

from lsst.ts import tcpip, utils

from .controller import Controller, VentGateState

T = TypeVar("T", bool, int, float, str)


def cast_string_to_type(new_type: Type[T], value: str) -> T:
    """Converts the value string to the specified type. In the case of boolean,
    "True" or "T" or "1" is ``True`` and everything else is ``False``. Other
    cases are handled by cast.

    Parameters
    ----------
    t: type
        The type that value should be converted to.

    value: str
        The value to be converted.

    Returns
    -------
    T
        The value represented in the string, converted to the specfied type.

    Raises
    ------
    ValueError
        If the value cannot be converted to the specified type.
    """

    if new_type is bool:  # Boolean is a special case
        if value.lower() in ("true", "t", "1"):
            return new_type(True)
        elif value.lower() in ("false", "f", "0"):
            return new_type(False)
        raise ValueError(
            "Expected bool value "
            + "('true', 't', '1', 'false', 'f', '0')"
            + " but got {value}"
        )
    return new_type(value)


class Dispatcher(tcpip.OneClientReadLoopServer):
    """A class representing a TCP server that accepts ATBuilding commands
    and dispatches them to relevant methods to make appropriate calls
    to the ``Controller``.

    Communication between the client and server take the form of ASCII strings
    terminated by newline. Commands are received in the form

    .. code-block::
        name_of_the_command arg1 arg2 arg3

    And responses take the form of JSON.
    """

    def __init__(
        self, port: int, log: logging.Logger, controller: Controller | None = None
    ):
        self.dispatch_dict: Final[dict[str, list[type]]] = {
            "close_vent_gate": [int, int, int, int],
            "open_vent_gate": [int, int, int, int],
            "get_fan_drive_max_frequency": [],
            "reset_extraction_fan_drive": [],
            "set_extraction_fan_drive_freq": [float],
            "set_extraction_fan_manual_control_mode": [bool],
            "start_extraction_fan": [],
            "stop_extraction_fan": [],
            "ping": [],
        }
        self.controller = controller if controller is not None else Controller()

        self.monitor_sleep_task = utils.make_done_future()

        self.telemetry_count = 0
        self.TELEMETRY_INTERVAL = 100

        super().__init__(
            port=port,
            host="0.0.0.0",
            log=log,
            connect_callback=self.on_connect,
            terminator=b"\r",
        )

    async def respond(self, message: str) -> None:
        await self.write_str(message + "\r\n")

    async def read_and_dispatch(self) -> None:
        """Read, parse and execute a command, and send a response."""
        data = await self.read_str()
        data = data.strip()
        if not data:
            return

        self.log.debug(f"Received command: {data!r}")

        command, *args = (
            data.split()
        )  # Tokenize the command and break out the first word as the method.
        if command not in self.dispatch_dict:
            # If the command string is not in the dictionary, send back an
            # error and do nothing.
            await self.respond(
                json.dumps(
                    dict(
                        command=command,
                        error=1,
                        exception_name="NotImplementedError",
                        message="No such command",
                        traceback="",
                    )
                )
            )
            return

        # Pull the handler and the argument list from the dictionary.
        types = self.dispatch_dict[command]
        if len(args) != len(types):
            # If the arguments don't match the list in the dictionary, send
            # back an error.
            await self.respond(
                json.dumps(
                    dict(
                        command=command,
                        error=1,
                        exception_name="TypeError",
                        message=f"Error while handling command {command}.",
                        traceback="",
                    )
                )
            )
            return

        try:
            # Convert the arguments to their expected type.
            args = [cast_string_to_type(t, arg) for t, arg in zip(types, args)]
            # Call the method with the specified arguments.
            return_value = await getattr(self, command)(*args)
            # Send back a success response.
            await self.respond(
                json.dumps(
                    dict(
                        command=command,
                        return_value=return_value,
                        error=0,
                        exception_name="",
                        message="",
                        traceback="",
                    )
                )
            )
        except Exception as e:
            self.log.exception(f"Exception raised while handling command {command}")
            await self.respond(
                json.dumps(
                    dict(
                        command=command,
                        error=1,
                        exception_name=type(e).__name__,
                        message=str(e),
                        traceback=traceback.format_exc(),
                    )
                )
            )

    async def close_vent_gate(
        self, gate0: int, gate1: int, gate2: int, gate3: int
    ) -> None:
        for gate in (gate0, gate1, gate2, gate3):
            if gate >= 0 and gate <= 3:
                self.controller.vent_close(gate)
            else:
                if gate != -1:
                    raise ValueError(f"Invalid vent ({gate}) must be between 0 and 3.")

    async def open_vent_gate(
        self, gate0: int, gate1: int, gate2: int, gate3: int
    ) -> None:
        for gate in (gate0, gate1, gate2, gate3):
            if gate >= 0 and gate <= 3:
                self.controller.vent_open(gate)
            else:
                if gate != -1:
                    raise ValueError(f"Invalid vent ({gate}) must be between 0 and 3.")

    async def get_fan_drive_max_frequency(self) -> float:
        return self.controller.get_max_frequency()

    async def reset_extraction_fan_drive(self) -> None:
        await self.controller.vfd_fault_reset()

    async def set_extraction_fan_drive_freq(self, target_frequency: float) -> None:
        await self.controller.set_fan_frequency(target_frequency)

    async def set_extraction_fan_manual_control_mode(
        self, enable_manual_control_mode: bool
    ) -> None:
        await self.controller.fan_manual_control(enable_manual_control_mode)

    async def start_extraction_fan(self) -> None:
        await self.controller.start_fan()

    async def stop_extraction_fan(self) -> None:
        await self.controller.stop_fan()

    async def ping(self) -> None:
        pass

    async def on_connect(self, bcs: tcpip.BaseClientOrServer) -> None:
        if self.connected:
            self.log.info("Connected to client.")
            asyncio.create_task(self.monitor_status())
        else:
            self.log.info("Disconnected from client.")

    async def monitor_status(self) -> None:
        vent_state = None
        last_fault = None
        fan_drive_state = None
        fan_frequency = None
        drive_voltage = None

        while self.connected:
            try:
                new_vent_state = [VentGateState.CLOSED] * 4
                for i in range(4):
                    try:
                        new_vent_state[i] = self.controller.vent_state(i)
                    except ValueError:
                        # Ignore non-configured vents
                        pass
                last8faults = await self.controller.last8faults()
                new_last_fault = last8faults[0][
                    0
                ]  # controller.last8faults returns tuple[int, str]

                new_fan_drive_state = await self.controller.get_drive_state()
            except Exception as e:
                self.log.exception(e)
                # Do not re-raise, so that the loop will continue

            # Check whether the vent state has changed
            if vent_state != new_vent_state:
                self.log.info(f"Vent state changed: {vent_state} -> {new_vent_state}")
                data = [int(state) for state in new_vent_state]
                await self.respond(
                    json.dumps(
                        dict(
                            command="evt_vent_gate_state",
                            error=0,
                            exception_name="",
                            message="",
                            traceback="",
                            data=data,
                        )
                    )
                )
                vent_state = new_vent_state

            # Check whether the last fault has changed
            if last_fault != new_last_fault:
                self.log.info(f"Last fault changed: {last_fault} -> {new_last_fault}")
                await self.respond(
                    json.dumps(
                        dict(
                            command="evt_extraction_fan_drive_fault_code",
                            error=0,
                            exception_name="",
                            message="",
                            traceback="",
                            data=new_last_fault,
                        )
                    )
                )
                last_fault = new_last_fault

            # Check whether the fan drive state has changed
            if fan_drive_state != new_fan_drive_state:
                self.log.debug(
                    f"Fan drive state changed: {fan_drive_state} -> {new_fan_drive_state}"
                )
                await self.respond(
                    json.dumps(
                        dict(
                            command="evt_extraction_fan_drive_state",
                            error=0,
                            exception_name="",
                            message="",
                            traceback="",
                            data=new_fan_drive_state,
                        )
                    )
                )
                fan_drive_state = new_fan_drive_state

            # Send telemetry every TELEMETRY_INTERVAL times through the loop
            self.telemetry_count -= 1
            new_fan_frequency = await self.controller.get_fan_frequency()
            new_drive_voltage = await self.controller.get_drive_voltage()
            if (
                self.telemetry_count < 0
                or new_fan_frequency != fan_frequency
                or new_drive_voltage != drive_voltage
            ):
                fan_frequency = new_fan_frequency
                drive_voltage = new_drive_voltage
                self.telemetry_count = self.TELEMETRY_INTERVAL
                telemetry = {
                    "tel_extraction_fan": new_fan_frequency,
                    "tel_drive_voltage": new_drive_voltage,
                }
                await self.respond(
                    json.dumps(
                        dict(
                            command="telemetry",
                            error=0,
                            exception_name="",
                            message="",
                            traceback="",
                            data=telemetry,
                        )
                    )
                )

            try:
                self.monitor_sleep_task = asyncio.ensure_future(asyncio.sleep(0.1))
                await self.monitor_sleep_task
            except asyncio.CancelledError:
                continue

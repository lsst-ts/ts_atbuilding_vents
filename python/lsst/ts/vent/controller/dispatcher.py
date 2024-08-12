import json
import logging
import traceback

from lsst.ts import tcpip

from .controller import Controller


def _cast_string_to_type(new_type: type, value: str):
    """Converts the value string to the specified type. In the case of boolean,
    "True" or "T" or "1" is ``True`` and everything else is ``False``. Other
    cases are handled by cast.

    Parameters
    ----------
    t: type
        The type that value should be converted to.

    value: str
        The value to be converted.

    Raises
    ------
    ValueError
        If the value cannot be converted to the specified type.
    """

    if new_type is bool:  # Boolean is a special case
        return value.lower() in ("true", "t", "1")
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
        self.dispatch_dict = {
            "close_vent_gate": [int],
            "open_vent_gate": [int],
            "reset_extraction_fan_drive": [],
            "set_extraction_fan_drive_freq": [float],
            "set_extraction_fan_manual_control_mode": [bool],
            "start_extraction_fan": [],
            "stop_extraction_fan": [],
            "ping": [],
        }
        self.controller = controller if controller is not None else Controller()

        super().__init__(port=port, log=log, terminator=b"\r")

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
            args = [_cast_string_to_type(t, arg) for t, arg in zip(types, args)]
            # Call the method with the specified arguments.
            await getattr(self, command)(*args)
            # Send back a success response.
            await self.respond(
                json.dumps(
                    dict(
                        command=command,
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

    async def close_vent_gate(self, gate: int) -> None:
        self.controller.vent_close(gate)

    async def open_vent_gate(self, gate: int) -> None:
        self.controller.vent_open(gate)

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

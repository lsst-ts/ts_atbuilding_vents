import logging
import traceback

from lsst.ts import tcpip

from .controller import Controller

def _type_convert(t: type, value: str):
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
    
    if t == bool:  # Boolean is a special case
        return value.lower() in ("true", "t", "1") 
    return t(value)

class Dispatcher(tcpip.OneClientReadLoopServer):
    def __init__(self, port: int, log: logging.Logger, controller: Controller = Controller()):
        self.dispatch_dict = {
            "closeVentGate": [int],
            "openVentGate": [int],
            "resetExtractionFanDrive": [],
            "setExtractionFanDriveFreq": [float],
            "setExtractionFanManualControlMode": [bool],
            "startExtractionFan": [],
            "stopExtractionFan": [],
            "ping": [],
        }
        self.controller = controller

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
        print(f"Received command: {data!r}")

        command, *args = data.split()
        if command not in self.dispatch_dict:
            await self.respond(f"{command} raise NotImplementedError()")
            return

        types = self.dispatch_dict[command]
        if len(args) != len(types):
            await self.respond(f"{command} raise TypeError('{command} expected {len(types)} arguments')")
            return

        try:
            args = [ _type_convert(t, arg) for t, arg in zip(types, args) ]
            await getattr(self, command)(*args)
            await self.respond(f"{command} OK")
            print(f"{command} OK")
        except Exception as e:
            exc_formatted = traceback.format_exception(type(e), e, e.__traceback__)
            for ef in exc_formatted:
                self.log.exception(ef)
            await self.respond(f"{command} raise {e!r}")

    async def closeVentGate(self, gate: int) -> None: 
        self.controller.vent_close(gate)

    async def openVentGate(self, gate: int) -> None: 
        self.controller.vent_open(gate)

    async def resetExtractionFanDrive(self) -> None: 
        await self.controller.vfd_fault_reset()

    async def setExtractionFanDriveFreq(self, targetFrequency: float) -> None:
        await self.controller.set_fan_frequency(targetFrequency)

    async def setExtractionFanManualControlMode(self, enableManualControlMode: bool) -> None:
        await self.controller.fan_manual_control(enableManualControlMode)

    async def startExtractionFan(self) -> None:
        await self.controller.start_fan()

    async def stopExtractionFan(self) -> None:
        await self.controller.stop_fan()

    async def ping(self) -> None:
        pass

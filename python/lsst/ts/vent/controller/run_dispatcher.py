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

import argparse
import asyncio
import logging

from .config import Config
from .controller import Controller
from .dispatcher import Dispatcher


def parse_args() -> argparse.Namespace:
    """Parses command line arguments.

    This function can be used with `async_main()`
    to parse the command line arguments for
    setup of the Raspberry Pi.

    Returns
    -------
    `argparse.Namespace`:
        The parsed command line arguments.

    """
    parser = argparse.ArgumentParser(
        prog="ts_atbuilding_vents",
        description="Controls dome vents and exhaust fan via the RPi.",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=23,
        help="Raspberry Pi port to listen for tcp commands.",
    )
    parser.add_argument(
        "--modbus-host",
        type=str,
        default=Config.hostname,
        help="Modbus hostname for the fan drive.",
    )
    parser.add_argument(
        "--modbus-port",
        type=int,
        default=Config.port,
        help="Modbus port number for the fan drive.",
    )
    parser.add_argument(
        "--modbus-device-id",
        type=int,
        default=Config.device_id,
        help="Modbus device ID for the fan drive.",
    )

    parser.add_argument(
        "--max-freq",
        type=float,
        default=Config.max_freq,
        help="Maximum fan frequency (Hz).",
    )

    parser.add_argument(
        "--megaind_address",
        type=int,
        default=Config.megaind_bus,
        help="Megaind card bus address.",
    )

    parser.add_argument(
        "--megaind_stack_level",
        type=int,
        default=Config.megaind_stack,
        help="Megaind card stack level.",
    )

    parser.add_argument(
        "--sixteen_address",
        type=int,
        default=Config.sixteen_bus,
        help="16inp card bus address.",
    )

    parser.add_argument(
        "--sixteen_stack_level",
        type=int,
        default=Config.sixteen_stack,
        help="16inp card stack level.",
    )

    return parser.parse_args()


async def async_main() -> None:
    """Sets up and invokes a dispatcher.

    This function can be used from the command line to create
    a hardware controller and dispatcher for the ATBuilding
    Raspberry Pi.

    """
    args = parse_args()
    log = logging.getLogger()

    # Set up configuration
    cfg = Config()
    cfg.hostname = args.modbus_host
    cfg.port = args.modbus_port
    cfg.device_id = args.modbus_device_id
    cfg.max_freq = args.max_freq
    cfg.megaind_bus = args.megaind_address
    cfg.megaind_stack = args.megaind_stack_level
    cfg.sixteen_bus = args.sixteen_address
    cfg.sixteen_stack = args.sixteen_stack_level

    # Set up controller
    controller = Controller(cfg, simulate=True)
    await controller.connect()

    # Set up dispatcher and attach controller
    Dispatcher(port=args.port, log=log, controller=controller)


def main() -> None:
    asyncio.run(async_main())

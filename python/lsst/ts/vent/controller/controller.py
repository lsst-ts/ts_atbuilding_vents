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
import os
import pymodbus.client

import config as cfg
from vfd import *

__all__ = ["Controller"]
logger = logging.getLogger(__name__)


class Controller:
    """ A controller that commands the components associated with the AT dome vents and fans.
        The code in this class is meant to run on the Raspberry Pi described in 
        https://confluence.lsstcorp.org/display/~fritzm/Auxtel+Vent+Gate+Automation
    """

    def __init__(self):
        """ Constructor. """
        logger.debug("__init__")
        self.vfd_hostname = cfg.VFD_HOSTNAME
        if "VFD_HOSTNAME" in os.environ:
            vfd_hostname = os.environ["VFD_HOSTNAME"]
        self.vfd_client = pymodbus.client.ModbusTcpClient(vfd_hostname)
        self.vfd_slave = cfg.VFD_SLAVE
        self.default_fan_frequency = cfg.VFD_MAX_FREQ

    @property
    def vfd_manual_control(self) -> bool:
        """ Returns the VFD setting for manual or automatic (modbus) control.

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
                self.vfd_client.read_holding_registers(
                    slave=self.vfd_slave, address=addr
                ).registers[0]
                for addr in CFG_REGISTERS
            ]
        )
        if settings == VFD_MANUAL:
            return True
        if settings == VFD_AUTO:
            return False
        logger.warning("Invalid settings in VFD")
        raise ValueError("Invalid settings in VFD")

    @vfd_manual_control.setter
    def vfd_manual_control(self, manual: bool) -> None:
        """ Sets the VFD for manual or automatic (modbus) control.

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
            self.vfd_client.write_register(
                slave=self.vfd_slave, address=address, value=value
            )

    def start_fan(self):
        """ Starts the dome exhaust fan

            Raises
            ======
            ModbusException if a communications error occurs
        """
        logger.debug("start_fan()")
        self.fan_frequency = self.default_fan_frequency

    def stop_fan(self):
        """ Stops the dome exhaust fan

            Raises
            ======
            ModbusException if a communications error occurs
        """
        logger.debug("stop_fan()")
        self.fan_frequency = 0.0

    @property
    def fan_frequency(self) -> float:
        """ Returns the target frequency configured in the VFD.

            Raises
            ======
            ModbusException if a communications error occurs
        """


        logger.debug("get fan_frequency")
        cmd = self.vfd_client.read_holding_registers(
            slave=self.vfd_slave, address=CMD_REGISTER
        ).registers[0]
        if cmd == 0:
            return 0.0

        lfr = self.vfd_client.read_holding_registers(
            slave=self.vfd_slave, address=LFR_REGISTER
        ).registers[0]
        return 0.1 * lfr

    @fan_frequency.setter
    def fan_frequency(self, frequency: float) -> None:
        """ Sets the target frequency for the dome exhaust fan. The frequency must be between
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
            CMD_REGISTER: 0 if frequency == 0.0 else 1,
            LFR_REGISTER: round(frequency * 10),
        }
        for address, value in settings.items():
            self.vfd_client.write_register(
                slave=self.vfd_slave, address=address, value=value
            )

    def vfd_fault_reset(self) -> None:
        """ Resets a fault condition on the VFD so that it will operate again.

            Raises
            ======
            ModbusException if a communications error occurs
        """

        for address, value in FAULT_RESET_SEQUENCE:
            self.vfd_client.write_register(
                slave=self.vfd_slave, address=address, value=value
            )

    @property
    def last8faults(self) -> list[tuple[int, str]]:
        """ Returns the last eight fault conditions recorded by the VFD

            Returns
            =======
            A list containing 8 tuples each with length 2. The first element in the tuple is
            an integer fault code, and the second is a human-readable description of the fault code.

            Raises
            ======
            ModbusException if a communications error occurs
        """


        logger.debug("last8faults")
        return [
            (r, VFD_FAULTS[r])
            for r in client.read_holding_registers(
                slave=1, address=FAULT_REGISTER, count=8
            ).registers
        ]

    

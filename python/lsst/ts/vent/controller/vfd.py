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

from enum import IntEnum


class Registers(IntEnum):
    SLL_REGISTER = 7010
    RSF_REGISTER = 7124
    FAULT_REGISTER = 7201
    CHCF_REGISTER = 8401
    FR1_REGISTER = 8413
    CD1_REGISTER = 8423
    CMD_REGISTER = 8501
    LFR_REGISTER = 8502
    LFRD_REGISTER = 8602

    


# Manual / auto VFD settings:
# FR1             CHCF       CD1            RSF           SLL
# 8413            8401       8423           7124          7010
# 1 = A1          1 = SIN    1 = TER        0 = NO        1 = YES
# 164 = modbus    3 = IO     10 = modbus    162 = CD02    0 = NO
CFG_REGISTERS = (
    Registers.FR1_REGISTER,
    Registers.CHCF_REGISTER,
    Registers.CD1_REGISTER,
    Registers.RSF_REGISTER,
    Registers.SLL_REGISTER,
)
""" The registers used to configure the VFD for manual or modbus-controlled operation. """
VFD_MANUAL = (1, 1, 1, 0, 1)
""" The settings used for manual operation. """
VFD_AUTO = (
    164,
    3,
    10,
    162,
    0,
)
""" The settings used for automatic operation. """

FAULT_RESET_SEQUENCE = (
    (Registers.CMD_REGISTER, 0),
    (Registers.LFRD_REGISTER, 0),
    (Registers.CMD_REGISTER, 4),
    (Registers.LFRD_REGISTER, 0),
    (Registers.CMD_REGISTER, 0),
    (Registers.LFRD_REGISTER, 0),
)
""" The settings needed to reset after a VFD fault """

VFD_FAULTS = {
    0: "No fault saved",
    2: "EEprom control fault",
    3: "Incorrect configuration",
    4: "Invalid config parameters",
    5: "Modbus coms fault",
    6: "Com Internal link fault",
    7: "Network fault",
    8: "External fault logic input",
    9: "Overcurrent fault",
    10: "Precharge",
    11: "Speed feedback loss",
    12: "Output speed <> ref",
    16: "Drive overheating fault",
    17: "Motor overload fault",
    18: "DC bus overvoltage fault",
    19: "Supply overvoltage fault",
    20: "1 motor phase loss fault",
    21: "Supply phase loss fault",
    22: "Supply undervolt fault",
    23: "Motor short circuit",
    24: "Motor overspeed fault",
    25: "Auto-tuning fault",
    26: "Rating error",
    27: "Incompatible control card",
    28: "Internal coms link fault",
    29: "Internal manu zone fault",
    30: "EEprom power fault",
    32: "Ground short circuit",
    33: "3 motor phase loss fault",
    34: "Comms fault CANopen",
    35: "Brake control fault",
    38: "External fault comms",
    41: "Brake feedback fault",
    42: "PC coms fault",
    44: "Torque/current limit fault",
    45: "HMI coms fault",
    49: "LI6=PTC failed",
    50: "LI6=PTC overheat fault",
    51: "Internal I measure fault",
    52: "Internal i/p volt circuit flt",
    53: "Internal temperature fault",
    54: "IGBT overheat fault",
    55: "IGBT short circuit fault",
    56: "motor short circuit",
    58: "Output cont close fault",
    59: "Output cont open fault",
    64: "input contactor",
    67: "IGBT desaturation",
    68: "Internal option fault",
    69: "internal- CPU ",
    71: "AI3 4-20mA loss",
    73: "Cards pairing",
    76: "Dynamic load fault",
    77: "Interrupted config.",
    99: "Channel switching fault",
    100: "Process Underlaod Fault",
    101: "Process Overload Fault",
    105: "Angle error",
    107: "Safety fault",
    108: "FB fault",
    109: "FB stop fault",
}
""" VFD Fault code descriptions """

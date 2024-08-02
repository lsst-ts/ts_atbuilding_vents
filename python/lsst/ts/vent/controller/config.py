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

VFD_HOSTNAME = "auxtel-vent-fan01"
""" The default VFD hostname to connect to via modbus-TCP """

VFD_PORT = 502
""" The default VFD TCP port to connect to via modbus-TCP """

VFD_SLAVE = 1
""" The default modbus slave ID for the VFD """

VFD_MAX_FREQ = 20.0
""" Default maximum frequency for the dome fans """

MEGAIND_STACK = 1
""" The stack level of the megaind card (selectable
from address jumpers [0..7])
"""

VENT_SIGNAL_CH = [4, -1, -1, -1]
""" I/O Channel open signal for the four vents on the
Industrial Automation RPi hat opto-outputs
"""

VENT_OPEN_LIMIT_CH = [1, -1, -1, -1]
""" I/O Channel open limits for the four vents, on the
Industrial Automation RPi hat opto-inputs
"""

VENT_CLOSE_LIMIT_CH = [2, -1, -1, -1]
""" I/O Channel close limits for the four vents, on the
Industrial Automation RPi hat opto-inputs
"""

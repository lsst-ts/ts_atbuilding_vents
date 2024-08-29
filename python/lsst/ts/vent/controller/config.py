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


class Config:
    hostname = "localhost"
    """The default hostname to connect to via modbus-TCP."""

    port = 502
    """The default TCP port to connect to via modbus-TCP."""

    device_id = 1
    """The default modbus device ID for the variable frequency drive."""

    max_freq = 50.0
    """Default maximum frequency for the dome fans."""

    megaind_bus = 1
    """Bus number for the megaind card."""

    megaind_stack = 1
    """The stack level (i2c target address) of the megaind card."""

    sixteen_bus = 2
    """Bus number for the 16inp card."""

    sixteen_stack = 1
    """The stack level (i2c target address) of the 16inp card."""

    vent_signal_ch = [4, -1, -1, -1]
    """I/O Channel open signal for the four vents on the opto-outputs."""

    vent_open_limit_ch = [1, -1, -1, -1]
    """I/O Channel open limits for the four vents, on the opto-inputs."""

    vent_close_limit_ch = [2, -1, -1, -1]
    """I/O Channel close limits for the four vents, on the opto-inputs."""

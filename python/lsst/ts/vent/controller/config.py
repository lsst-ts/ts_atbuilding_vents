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

    modbus_timeout = 1.0
    """Timeout, in seconds, for a single modbus transaction.

    This is deliberately shorter than the pymodbus default of 3 seconds:
    ``Dispatcher.monitor_status`` polls the drive ten times per second, so a
    long timeout would cause polls to queue up behind an unresponsive drive.
    """

    modbus_retries = 3
    """Number of times pymodbus retries a single modbus transaction."""

    reconnect_delay = 0.1
    """Initial delay, in seconds, before pymodbus retries a lost connection.

    pymodbus doubles this delay after each failed attempt, up to
    `reconnect_delay_max`. Set to 0 to disable automatic reconnection.
    """

    reconnect_delay_max = 60.0
    """Maximum delay, in seconds, between pymodbus reconnection attempts."""

    connect_max_time = 300.0
    """How long, in seconds, `Controller.connect` retries the initial
    connection to the variable frequency drive before giving up.

    pymodbus only reconnects automatically once a connection has been
    established and then lost; it does not retry the initial connection. This
    covers the case where the drive is not yet powered up when the controller
    starts.
    """

    max_freq = 50.0
    """Default maximum frequency for the dome fans."""

    megaind_bus = 1
    """Bus number for the megaind card."""

    megaind_stack = 0
    """The stack level (i2c target address) of the megaind card."""

    sixteen_bus = 1
    """Bus number for the 16inp card."""

    sixteen_stack = 1
    """The stack level (i2c target address) of the 16inp card."""

    vent_signal_ch = [1, 2, 3, 4]
    """I/O Channel open signal for the four vents on the opto-outputs."""

    vent_open_limit_ch = [15, 13, 11, 9]
    """I/O Channel open limits for the four vents, on the opto-inputs."""

    vent_close_limit_ch = [16, 14, 12, 10]
    """I/O Channel close limits for the four vents, on the opto-inputs."""

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

import socket
import unittest

from lsst.ts.vent.controller import Config, Controller
from pymodbus.exceptions import ConnectionException

# How long to let `Controller.connect` retry before giving up, in seconds.
# The production default is five minutes, which is far too long for a test.
CONNECT_MAX_TIME = 1.0


def closed_port() -> int:
    """Returns a TCP port on localhost with nothing listening on it."""
    with socket.socket() as sock:
        sock.bind(("localhost", 0))
        return sock.getsockname()[1]


class TestConnect(unittest.IsolatedAsyncioTestCase):
    """Tests the retry and give-up behavior of `Controller.connect`."""

    async def test_gives_up_after_connect_max_time(self) -> None:
        """An unreachable drive raises `ConnectionException` rather than
        retrying forever.
        """
        cfg = Config()
        cfg.hostname = "localhost"
        cfg.port = closed_port()
        cfg.connect_max_time = CONNECT_MAX_TIME
        controller = Controller(cfg)

        with self.assertRaises(ConnectionException):
            await controller.connect()

        self.assertFalse(controller.connected)

    async def test_retries_before_giving_up(self) -> None:
        """Connecting to an unreachable drive is retried, not attempted
        once.
        """
        cfg = Config()
        cfg.hostname = "localhost"
        cfg.port = closed_port()
        cfg.connect_max_time = CONNECT_MAX_TIME
        controller = Controller(cfg)

        retries = 0

        def count_retry(details: dict) -> None:
            nonlocal retries
            retries += 1

        controller._log_connect_retry = count_retry  # type: ignore[method-assign]

        with self.assertRaises(ConnectionException):
            await controller.connect()

        self.assertGreater(retries, 0)

    async def test_failed_connect_stops_the_simulator(self) -> None:
        """A failed connection leaves nothing behind."""
        cfg = Config()
        cfg.connect_max_time = CONNECT_MAX_TIME
        controller = Controller(cfg, simulate=True)

        # Point the client, but not the simulator, at a dead port. The
        # simulator reads its own port from simulator_setup.json.
        controller.config.port = closed_port()

        with self.assertRaises(ConnectionException):
            await controller.connect()

        second = Controller(Config(), simulate=True)
        try:
            await second.connect()
            self.assertTrue(second.connected)
        finally:
            await second.stop()


if __name__ == "__main__":
    unittest.main()

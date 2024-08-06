import unittest
from unittest.mock import patch

from lsst.ts.vent.controller import Config, Controller, VentGateState

input_bits = [0, 0, 0, 0]


def getOptoCh(stack: int, channel: int) -> int:
    global input_bits

    channel -= 1  # Channels are 1-indexed

    assert stack == Config.megaind_stack
    assert 0 <= channel <= 3
    return input_bits[channel]


def setOd(stack: int, channel: int, val: int) -> None:
    global input_bits

    channel -= 1  # Channels are 1-indexed

    assert stack == Config.megaind_stack
    assert 0 <= channel <= 3
    assert val == 0 or val == 1
    vent_number = [i for i in range(4) if Config.vent_signal_ch[i] - 1 == channel]
    assert len(vent_number) <= 1
    if len(vent_number) == 1:
        vent_number = vent_number[0]
        op = val
        cl = 0 if val else 1
        input_bits[Config.vent_open_limit_ch[vent_number] - 1] = op
        input_bits[Config.vent_close_limit_ch[vent_number] - 1] = cl


class TestLouvres(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.patch_getOptCh = patch("megaind.getOptoCh", getOptoCh)
        self.patch_setOd = patch("megaind.setOd", setOd)
        self.patch_getOptCh.start()
        self.patch_setOd.start()
        self.controller = Controller()

    async def asyncTearDown(self):
        self.patch_getOptCh.stop()
        self.patch_setOd.stop()

    async def test_vent_open(self):
        self.controller.vent_open(0)
        self.assertEqual(self.controller.vent_state(0), VentGateState.OPEN)

    async def test_vent_close(self):
        self.controller.vent_close(0)
        self.assertEqual(self.controller.vent_state(0), VentGateState.CLOSED)

    async def test_vent_partiallyopen(self):
        global input_bits
        input_bits = [0, 0, 0, 0]
        self.assertEqual(self.controller.vent_state(0), VentGateState.PARTIALLY_OPEN)

    async def test_vent_invalidstate(self):
        global input_bits
        input_bits = [1, 1, 1, 1]
        self.assertEqual(self.controller.vent_state(0), VentGateState.FAULT)

    def test_vent_invalidvent(self):
        with self.assertRaises(ValueError):
            self.controller.vent_open(1000000)
        with self.assertRaises(ValueError):
            self.controller.vent_close(1000000)
        with self.assertRaises(ValueError):
            self.controller.vent_state(1000000)

    async def test_non_configured_vent(self):
        with self.assertRaises(ValueError):
            self.controller.vent_open(1)
        with self.assertRaises(ValueError):
            self.controller.vent_close(1)
        with self.assertRaises(ValueError):
            self.controller.vent_state(1)

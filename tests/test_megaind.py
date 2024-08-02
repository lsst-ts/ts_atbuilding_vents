import unittest
from unittest.mock import patch

import lsst.ts.vent.controller.config as cfg
from lsst.ts.vent.controller import Controller, VentGateState

input_bits = [0, 0, 0, 0]

def getOptoCh(stack: int, channel: int) -> int:
    global input_bits

    channel -= 1 # Channels are 1-indexed

    assert stack == cfg.MEGAIND_STACK
    assert 0 <= channel <= 3
    return input_bits[channel]

def set0_10Out(stack: int, channel: int, value: float) -> None:
    global input_bits

    channel -= 1 # Channels are 1-indexed

    assert stack == cfg.MEGAIND_STACK
    assert 0 <= channel <= 3
    assert 0 <= value <= 10.0
    vent_number = [ i for i in range(4) if cfg.VENT_SIGNAL_CH[i]-1 == channel]
    assert len(vent_number) <= 1
    if len(vent_number) == 1:
        vent_number = vent_number[0]
        op = 1 if value > 5 else 0
        cl = 0 if value > 5 else 1
        input_bits[cfg.VENT_OPEN_LIMIT_CH[vent_number]-1] = op
        input_bits[cfg.VENT_CLOSE_LIMIT_CH[vent_number]-1] = cl

class TestLouvres(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
       self.patch_getOptCh = patch("megaind.getOptoCh", getOptoCh)
       self.patch_set0_10Out = patch("megaind.set0_10Out", set0_10Out)
       self.patch_getOptCh.start()
       self.patch_set0_10Out.start()
       self.controller = Controller()
    
    async def asyncTearDown(self):
        self.patch_getOptCh.stop()
        self.patch_set0_10Out.stop()

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

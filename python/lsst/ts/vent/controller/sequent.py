# The MIT License (MIT)
#
# Copyright (c) 2020 Sequent Microsystems
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Copied from:
#     https://github.com/SequentMicrosystems/megaind-rpi
#     https://github.com/SequentMicrosystems/16inpind-rpi
# Added to the ts_atbuilding_vents repository 21 August 2024, Brian Brondel

__all__ = ["write_channel", "read_channel"]

import smbus3

INPUTS16_DEVICE_ADDRESS = 0x20  # Address of the 16inp device
INPUTS16_INPORT_REG_ADD = 0  # Command to read the input bit
pin16_mask = [
    0x8000,
    0x4000,
    0x2000,
    0x1000,
    0x0800,
    0x0400,
    0x0200,
    0x0100,
    0x80,
    0x40,
    0x20,
    0x10,
    0x08,
    0x04,
    0x02,
    0x01,
]

MEGA_DEVICE_ADDRESS = 0x50  # Address of the mega device

MEGA_MEM_RELAY_SET = 1  # Command to set the relay active
MEGA_MEM_RELAY_CLR = 2  # Command to set the relay inactive


def write_channel(bus_number: int, stack: int, channel: int, value: int) -> None:
    """Writes to the general purpose output on the megaind board.

    Parameters
    ----------
    bus_number : int
        The I2C bus number (the device will be at `/dev/i2c-{bus_number}`)

    stack : int
        Board stack number to write to, from 0 to 7.

    channel : int
        General purpose output channel, from 1 to 4.

    value : int
        Value to write to the output channel, either
        0 (low) or 1 (high)


    Raises
    ------
    OSError
        If there is a communication error.

    ValueError
        If an invalid stack or channel number is specified.
    """

    # Verify that the stack number is valid
    if stack < 0 or stack > 7:
        raise ValueError("Invalid stack level!")

    # Verify that the channel number is valid
    if channel < 1 or channel > 4:
        raise ValueError("Invalid channel number!")

    hwAdd = MEGA_DEVICE_ADDRESS + stack
    with smbus3.SMBus(bus_number) as bus:
        if value != 0:
            bus.write_byte_data(hwAdd, MEGA_MEM_RELAY_SET, channel)
        else:
            bus.write_byte_data(hwAdd, MEGA_MEM_RELAY_CLR, channel)


def read_channel(bus_number: int, stack: int, channel: int) -> int:
    """Reads the input for the specified board and channel number
    on the 16inpind board.

    Parameters
    ----------
    bus_number : int
        The I2C bus number (the device will be at `/dev/i2c-{bus_number}`)

    stack : int
        Stack number of the board to read.

    channel : int
        General purpose input channel number to read.

    Returns
    -------
    int
        1 if the input channel is active, or 0 otherwise.

    Raises
    ------
    OSError
        If there is a communication error.

    ValueError
        If an invalid stack or channel number is specified.
    """
    if stack < 0 or stack > 7:
        raise ValueError("Invalid stack level")
    stack = 0x07 ^ stack

    if channel < 1 or channel > 16:
        raise ValueError("Invalid channel")

    with smbus3.SMBus(bus_number) as bus:
        hw_add = INPUTS16_DEVICE_ADDRESS + stack
        val = bus.read_word_data(hw_add, INPUTS16_INPORT_REG_ADD)

    if val & pin16_mask[channel - 1] == 0:
        return 1
    return 0

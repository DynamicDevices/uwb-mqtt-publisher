#!/usr/bin/env python3
"""
UWB Serial Port Handling
Handles serial port connection, reading, writing, and device reset.
"""

import serial
import time
import sys


def connect_serial(uart, verbose=False):
    """
    Connect to serial port.

    Args:
        uart: Serial port path (e.g., '/dev/ttyUSB0')
        verbose: Enable verbose logging

    Returns:
        Serial port object or None on failure
    """
    try:
        ser = serial.serial_for_url(uart, do_not_open=True)
        ser.baudrate = 115200
        ser.bytesize = 8
        ser.parity = 'N'
        ser.stopbits = 1
        ser.rtscts = False
        ser.xonxoff = False
        ser.open()
        ser.dtr = False

    except serial.SerialException as e:
        if verbose:
            print(f"[ERROR] Serial connection failed: {e}")
        return None

    time.sleep(0.5)
    if verbose:
        print(f"[VERBOSE] Serial connection established: {ser.read(ser.in_waiting)}")

    return ser


def disconnect_serial(ser):
    """Disconnect from serial port."""
    if ser:
        ser.rts = False
        ser.close()
        ser.is_open = False


def flush_rx(ser):
    """Flush and read all available data from serial port."""
    try:
        n = ser.in_waiting
        msg = ser.read(n)
        return msg

    except serial.SerialException as e:
        print(f"[ERROR] Serial read error: {e}")
        disconnect_serial(ser)
        return b''


def reset_device(ser, verbose=False):
    """
    Reset the UWB device via DTR line.

    Args:
        ser: Serial port object
        verbose: Enable verbose logging
    """
    if verbose:
        print("[INFO] Resetting device...")
    ser.dtr = True
    time.sleep(0.1)
    ser.dtr = False


def write_serial(d, data):
    """Write data to serial port."""
    s = str(bytearray(data)) if sys.version_info < (3,) else bytes(data)
    return d.write(s)


def read_serial(d, nbytes):
    """Read data from serial port."""
    s = d.read(nbytes)
    return [ord(c) for c in s] if type(s) is str else list(s)

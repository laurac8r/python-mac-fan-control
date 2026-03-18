"""Shared pytest fixtures for mac_fan_control tests."""

import struct
from unittest.mock import MagicMock

import pytest

from mac_fan_control.smc import (
    decode_fpe2,
    decode_flt,
    decode_sp78,
    decode_ui8,
    decode_ui16,
    decode_ui32,
)


# ---------------------------------------------------------------------------
# SMC data helpers – build raw byte payloads that mimic IOKit SMC responses
# ---------------------------------------------------------------------------

def make_fpe2_bytes(value: float) -> bytes:
    """Encode a float as Apple's fpe2 (unsigned 14.2 fixed-point, big-endian)."""
    raw = int(round(value * 4))
    return struct.pack(">H", raw)


def make_sp78_bytes(value: float) -> bytes:
    """Encode a float as Apple's sp78 (signed 8.8 fixed-point, big-endian)."""
    raw = int(round(value * 256))
    return struct.pack(">h", raw)


def make_flt_bytes(value: float) -> bytes:
    """Encode a float as a 4-byte native-endian (little-endian) IEEE 754 float."""
    return struct.pack("<f", value)


@pytest.fixture()
def smc_values() -> dict[str, tuple[bytes, str]]:
    """Provide a mutable dict of SMC key → (raw_bytes, data_type) for tests.

    Tests can customise this dict before injecting it into the mock SMC.
    Default dataset represents a MacBook Pro-like machine with 2 fans.
    """
    return {
        # Fan count
        "FNum": (struct.pack(">B", 2), "ui8 "),
        # Fan 0 – actual, min, max RPM (fpe2)
        "F0Ac": (make_fpe2_bytes(2160.0), "fpe2"),
        "F0Mn": (make_fpe2_bytes(1200.0), "fpe2"),
        "F0Mx": (make_fpe2_bytes(6156.0), "fpe2"),
        "F0Tg": (make_fpe2_bytes(0.0), "fpe2"),
        "F0Md": (struct.pack(">B", 0), "ui8 "),
        # Fan 1 – actual, min, max RPM (fpe2)
        "F1Ac": (make_fpe2_bytes(2000.0), "fpe2"),
        "F1Mn": (make_fpe2_bytes(1200.0), "fpe2"),
        "F1Mx": (make_fpe2_bytes(5900.0), "fpe2"),
        "F1Tg": (make_fpe2_bytes(0.0), "fpe2"),
        "F1Md": (struct.pack(">B", 0), "ui8 "),
        # Temperature sensors (sp78)
        "TC0P": (make_sp78_bytes(52.5), "sp78"),
        "TC0H": (make_sp78_bytes(54.0), "sp78"),
        "TG0P": (make_sp78_bytes(48.25), "sp78"),
        "Tm0P": (make_sp78_bytes(38.0), "sp78"),
        "TB0T": (make_sp78_bytes(33.5), "sp78"),
        # Total key count
        "#KEY": (struct.pack(">I", 120), "ui32"),
    }


@pytest.fixture()
def mock_smc_connection(smc_values: dict[str, tuple[bytes, str]]) -> MagicMock:
    """Return a MagicMock that behaves like an open SMC connection.

    The mock's ``read_key`` returns data from *smc_values*; ``write_key``
    records calls for later assertion.
    """
    conn = MagicMock(name="SMCConnection")

    def _read_key(key: str) -> tuple[bytes, str]:
        if key not in smc_values:
            from mac_fan_control.exceptions import SMCKeyNotFoundError
            raise SMCKeyNotFoundError(f"Key not found: {key}")
        return smc_values[key]

    _float_decoders: dict[str, callable] = {
        "fpe2": decode_fpe2,
        "sp78": decode_sp78,
        "flt ": decode_flt,
        "flt": decode_flt,
    }
    _int_decoders: dict[str, callable] = {
        "ui8 ": decode_ui8,
        "ui8": decode_ui8,
        "ui16": decode_ui16,
        "ui32": decode_ui32,
    }

    def _read_key_float(key: str) -> float:
        raw, dtype = _read_key(key)
        dec = _float_decoders.get(dtype) or _float_decoders.get(dtype.strip())
        if dec is None:
            from mac_fan_control.exceptions import SMCReadError
            raise SMCReadError(f"Cannot decode '{dtype}' as float")
        return dec(raw)

    def _read_key_int(key: str) -> int:
        raw, dtype = _read_key(key)
        dec = _int_decoders.get(dtype) or _int_decoders.get(dtype.strip())
        if dec is None:
            from mac_fan_control.exceptions import SMCReadError
            raise SMCReadError(f"Cannot decode '{dtype}' as int")
        return dec(raw)

    conn.read_key.side_effect = _read_key
    conn.read_key_float.side_effect = _read_key_float
    conn.read_key_int.side_effect = _read_key_int
    conn.write_key.return_value = None
    conn.close.return_value = None
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn

"""Low-level Apple SMC (System Management Controller) interface via IOKit.

This module provides:
- Codec functions for SMC data types (fpe2, sp78, flt, ui8, ui16, ui32).
- ``SMCConnection`` for reading/writing SMC keys through the AppleSMC IOKit driver.

Requires macOS and root/admin privileges for write operations.
"""

import ctypes
import ctypes.util
import struct
from ctypes import (
    POINTER,
    Structure,
    byref,
    c_char,
    c_int,
    c_size_t,
    c_uint,
    c_uint8,
    c_uint32,
    c_void_p,
)

from mac_fan_control.exceptions import (
    SMCConnectionError,
    SMCKeyNotFoundError,
    SMCReadError,
    SMCWriteError,
)

# ---------------------------------------------------------------------------
# IOKit C-level bindings
# ---------------------------------------------------------------------------

_iokit_path = ctypes.util.find_library("IOKit")
_iokit = ctypes.cdll.LoadLibrary(_iokit_path) if _iokit_path else None

_cf_path = ctypes.util.find_library("CoreFoundation")
_cf = ctypes.cdll.LoadLibrary(_cf_path) if _cf_path else None

_libc_path = ctypes.util.find_library("c")
_libc = ctypes.cdll.LoadLibrary(_libc_path) if _libc_path else None

KERNEL_INDEX_SMC = 2
SMC_CMD_READ_KEYINFO = 9
SMC_CMD_READ_BYTES = 5
SMC_CMD_WRITE_BYTES = 6

_KERN_SUCCESS = 0


class _SMCVersion(Structure):
    _fields_ = [
        ("major", c_char),
        ("minor", c_char),
        ("build", c_char),
        ("reserved", c_char),
        ("release", c_uint8 * 2),
    ]


class _SMCPLimitData(Structure):
    _fields_ = [
        ("version", c_uint8 * 2),
        ("length", c_uint8 * 2),
        ("cpuPLimit", c_uint32),
        ("gpuPLimit", c_uint32),
        ("memPLimit", c_uint32),
    ]


class _SMCKeyData_keyInfo(Structure):
    _fields_ = [
        ("dataSize", c_uint32),
        ("dataType", c_uint32),
        ("dataAttributes", c_uint8),
    ]


class _SMCKeyData(Structure):
    _fields_ = [
        ("key", c_uint32),
        ("vers", _SMCVersion),
        ("pLimitData", _SMCPLimitData),
        ("keyInfo", _SMCKeyData_keyInfo),
        ("result", c_uint8),
        ("status", c_uint8),
        ("data8", c_uint8),
        ("data32", c_uint32),
        ("bytes", c_uint8 * 32),
    ]


class _SMCVal(Structure):
    _fields_ = [
        ("key", (c_char * 5)),
        ("dataSize", c_uint32),
        ("dataType", (c_char * 5)),
        ("bytes", c_uint8 * 32),
    ]


def _str_to_uint32(s: str) -> int:
    """Convert a 4-char SMC key string to a uint32."""
    return struct.unpack(">I", s.encode("ascii")[:4])[0]


def _uint32_to_str(val: int) -> str:
    """Convert a uint32 back to a 4-char SMC key string."""
    return struct.pack(">I", val).decode("ascii")


# ---------------------------------------------------------------------------
# Thin wrappers around IOKit functions (easily patchable in tests)
# ---------------------------------------------------------------------------


def _setup_iokit_signatures() -> None:
    """Set argtypes and restype on IOKit functions once."""
    if _iokit is None:
        return

    # IOServiceMatching(name) -> CFMutableDictionaryRef (void*)
    _iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
    _iokit.IOServiceMatching.restype = c_void_p

    # IOServiceGetMatchingService(masterPort, matching) -> io_service_t (uint)
    _iokit.IOServiceGetMatchingService.argtypes = [c_uint, c_void_p]
    _iokit.IOServiceGetMatchingService.restype = c_uint

    # IOServiceOpen(service, owningTask, type, &connect) -> kern_return_t
    _iokit.IOServiceOpen.argtypes = [
        c_uint, c_uint, c_uint, POINTER(c_uint)
    ]
    _iokit.IOServiceOpen.restype = c_int

    # IOServiceClose(connect) -> kern_return_t
    _iokit.IOServiceClose.argtypes = [c_uint]
    _iokit.IOServiceClose.restype = c_int

    # IOConnectCallStructMethod(connect, selector, inputStruct, inputSize,
    #                           outputStruct, &outputSize) -> kern_return_t
    _iokit.IOConnectCallStructMethod.argtypes = [
        c_uint,  # connection
        c_uint,  # selector
        POINTER(_SMCKeyData),  # inputStruct
        c_size_t,  # inputStructCnt
        POINTER(_SMCKeyData),  # outputStruct
        POINTER(c_size_t),  # outputStructCnt
    ]
    _iokit.IOConnectCallStructMethod.restype = c_int


_setup_iokit_signatures()


def _mach_task_self() -> int:
    """Return the mach port for the current task.

    On macOS, ``mach_task_self()`` is a macro that reads the global
    variable ``mach_task_self_``.
    """
    if _libc is None:
        raise SMCConnectionError("libc not found")
    return c_uint.in_dll(_libc, "mach_task_self_").value


def IOServiceMatching(name: str) -> c_void_p:
    """Call IOServiceMatching from IOKit."""
    if _iokit is None:
        raise SMCConnectionError("IOKit library not found")
    return _iokit.IOServiceMatching(name.encode("utf-8"))


def IOServiceGetMatchingService(master_port: int, matching: c_void_p) -> int:
    """Call IOServiceGetMatchingService from IOKit."""
    if _iokit is None:
        raise SMCConnectionError("IOKit library not found")
    return _iokit.IOServiceGetMatchingService(c_uint(master_port), matching)


def IOServiceOpen(
        service: int, owning_task: int, conn_type: int
) -> tuple[int, int]:
    """Call IOServiceOpen from IOKit. Returns (kern_return, connection)."""
    if _iokit is None:
        raise SMCConnectionError("IOKit library not found")
    conn = c_uint()
    kr = _iokit.IOServiceOpen(
        c_uint(service), c_uint(owning_task), c_uint(conn_type), byref(conn)
    )
    return kr, conn.value


def IOServiceClose(connection: int) -> int:
    """Call IOServiceClose from IOKit."""
    if _iokit is None:
        raise SMCConnectionError("IOKit library not found")
    return _iokit.IOServiceClose(c_uint(connection))


def IOConnectCallStructMethod(
        connection: int,
        selector: int,
        input_struct: _SMCKeyData,
        output_struct: _SMCKeyData,
) -> int:
    """Call IOConnectCallStructMethod from IOKit."""
    if _iokit is None:
        raise SMCConnectionError("IOKit library not found")
    in_size = c_size_t(ctypes.sizeof(_SMCKeyData))
    out_size = c_size_t(ctypes.sizeof(_SMCKeyData))
    return _iokit.IOConnectCallStructMethod(
        c_uint(connection),
        c_uint(selector),
        byref(input_struct),
        in_size,
        byref(output_struct),
        byref(out_size),
    )


# ---------------------------------------------------------------------------
# SMC data type codecs
# ---------------------------------------------------------------------------


def decode_fpe2(data: bytes) -> float:
    """Decode fpe2 (unsigned 14.2 fixed-point, big-endian) to float.

    Args:
        data: Exactly 2 bytes of raw SMC data.

    Returns:
        Decoded float value.

    Raises:
        ValueError: If data is not exactly 2 bytes.
    """
    if len(data) != 2:
        raise ValueError(f"fpe2 requires exactly 2 bytes, got {len(data)}")
    raw = struct.unpack(">H", data)[0]
    return raw / 4.0


def encode_fpe2(value: float) -> bytes:
    """Encode a float to fpe2 (unsigned 14.2 fixed-point, big-endian).

    Args:
        value: Non-negative float value to encode.

    Returns:
        2 bytes of encoded data.

    Raises:
        ValueError: If value is negative.
    """
    if value < 0:
        raise ValueError("fpe2 requires a non-negative value")
    raw = int(round(value * 4))
    return struct.pack(">H", raw)


def decode_sp78(data: bytes) -> float:
    """Decode sp78 (signed 8.8 fixed-point, big-endian) to float.

    Args:
        data: Exactly 2 bytes of raw SMC data.

    Returns:
        Decoded float value.

    Raises:
        ValueError: If data is not exactly 2 bytes.
    """
    if len(data) != 2:
        raise ValueError(f"sp78 requires exactly 2 bytes, got {len(data)}")
    raw = struct.unpack(">h", data)[0]
    return raw / 256.0


def encode_sp78(value: float) -> bytes:
    """Encode a float to sp78 (signed 8.8 fixed-point, big-endian).

    Args:
        value: Float value to encode.

    Returns:
        2 bytes of encoded data.
    """
    raw = int(round(value * 256))
    return struct.pack(">h", raw)


def decode_flt(data: bytes) -> float:
    """Decode flt (4-byte native-endian IEEE 754 float).

    The SMC stores ``flt `` values in the platform's native byte order
    (little-endian on both Intel and Apple Silicon macOS).

    Args:
        data: Exactly 4 bytes of raw SMC data.

    Returns:
        Decoded float value.

    Raises:
        ValueError: If data is not exactly 4 bytes.
    """
    if len(data) != 4:
        raise ValueError(f"flt requires exactly 4 bytes, got {len(data)}")
    return struct.unpack("<f", data)[0]


def encode_flt(value: float) -> bytes:
    """Encode a float to flt (4-byte native-endian IEEE 754 float).

    Args:
        value: Float value to encode.

    Returns:
        4 bytes of encoded data.
    """
    return struct.pack("<f", value)


def decode_ui8(data: bytes) -> int:
    """Decode ui8 (unsigned 8-bit integer).

    Args:
        data: Exactly 1 byte.

    Returns:
        Decoded integer.

    Raises:
        ValueError: If data is not exactly 1 byte.
    """
    if len(data) != 1:
        raise ValueError(f"ui8 requires exactly 1 byte, got {len(data)}")
    return struct.unpack(">B", data)[0]


def decode_ui16(data: bytes) -> int:
    """Decode ui16 (unsigned 16-bit integer, big-endian).

    Args:
        data: Exactly 2 bytes.

    Returns:
        Decoded integer.

    Raises:
        ValueError: If data is not exactly 2 bytes.
    """
    if len(data) != 2:
        raise ValueError(f"ui16 requires exactly 2 bytes, got {len(data)}")
    return struct.unpack(">H", data)[0]


def decode_ui32(data: bytes) -> int:
    """Decode ui32 (unsigned 32-bit integer, big-endian).

    Args:
        data: Exactly 4 bytes.

    Returns:
        Decoded integer.

    Raises:
        ValueError: If data is not exactly 4 bytes.
    """
    if len(data) != 4:
        raise ValueError(f"ui32 requires exactly 4 bytes, got {len(data)}")
    return struct.unpack(">I", data)[0]


# ---------------------------------------------------------------------------
# Decoder dispatch table
# ---------------------------------------------------------------------------

_FLOAT_DECODERS: dict[str, callable] = {
    "fpe2": decode_fpe2,
    "sp78": decode_sp78,
    "flt ": decode_flt,
    "flt": decode_flt,
}

_INT_DECODERS: dict[str, callable] = {
    "ui8 ": decode_ui8,
    "ui8": decode_ui8,
    "ui16": decode_ui16,
    "ui32": decode_ui32,
}


# ---------------------------------------------------------------------------
# SMCConnection
# ---------------------------------------------------------------------------


class SMCConnection:
    """Context-managed connection to the AppleSMC IOKit driver.

    Usage::

        with SMCConnection() as smc:
            raw, dtype = smc.read_key("TC0P")
            temp = decode_sp78(raw)
    """

    def __init__(self) -> None:
        self._connection: int = 0
        self._is_open: bool = False

    # -- Context manager ---------------------------------------------------

    def __enter__(self) -> "SMCConnection":
        self.open()
        return self

    def __exit__(self, *_: object) -> bool:
        self.close()
        return False

    # -- Lifecycle ---------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """Return True if the connection is currently open."""
        return self._is_open

    def open(self) -> None:
        """Open a connection to the AppleSMC driver.

        Raises:
            SMCConnectionError: If the AppleSMC service is not found or
                cannot be opened.
        """
        matching = IOServiceMatching("AppleSMC")
        service = IOServiceGetMatchingService(0, matching)
        if service == 0:
            raise SMCConnectionError(
                "AppleSMC service not found — is this a real Mac?"
            )

        kr, conn = IOServiceOpen(service, _mach_task_self(), 0)
        if kr != _KERN_SUCCESS:
            raise SMCConnectionError(
                f"Failed to open AppleSMC service (kern_return={kr})"
            )

        self._connection = conn
        self._is_open = True

    def close(self) -> None:
        """Close the SMC connection."""
        if self._is_open:
            IOServiceClose(self._connection)
            self._connection = 0
            self._is_open = False

    # -- Read operations ---------------------------------------------------

    def read_key(self, key: str) -> tuple[bytes, str]:
        """Read a raw SMC key.

        Args:
            key: 4-character SMC key, e.g. ``"TC0P"``.

        Returns:
            Tuple of (raw_bytes, data_type_string).

        Raises:
            SMCConnectionError: If the connection is not open.
            SMCKeyNotFoundError: If the key does not exist.
            SMCReadError: If the read operation fails.
        """
        if not self._is_open:
            raise SMCConnectionError("SMC connection is not open")
        return self._call_read_key(key)

    def read_key_float(self, key: str) -> float:
        """Read an SMC key and decode it as a float.

        Supports data types: fpe2, sp78, flt.

        Args:
            key: 4-character SMC key.

        Returns:
            Decoded float value.

        Raises:
            SMCReadError: If the data type is not a known float type.
        """
        raw, dtype = self.read_key(key)
        dtype_stripped = dtype.strip()
        decoder = _FLOAT_DECODERS.get(dtype) or _FLOAT_DECODERS.get(
            dtype_stripped
        )
        if decoder is None:
            raise SMCReadError(
                f"Cannot decode key '{key}' type '{dtype}' as float"
            )
        return decoder(raw)

    def read_key_int(self, key: str) -> int:
        """Read an SMC key and decode it as an integer.

        Supports data types: ui8, ui16, ui32.

        Args:
            key: 4-character SMC key.

        Returns:
            Decoded integer value.

        Raises:
            SMCReadError: If the data type is not a known integer type.
        """
        raw, dtype = self.read_key(key)
        dtype_stripped = dtype.strip()
        decoder = _INT_DECODERS.get(dtype) or _INT_DECODERS.get(
            dtype_stripped
        )
        if decoder is None:
            raise SMCReadError(
                f"Cannot decode key '{key}' type '{dtype}' as int"
            )
        return decoder(raw)

    # -- Write operations --------------------------------------------------

    def write_key(self, key: str, data: bytes, data_type: str) -> None:
        """Write raw bytes to an SMC key.

        Args:
            key: 4-character SMC key.
            data: Raw bytes to write.
            data_type: SMC data type string (e.g. "fpe2").

        Raises:
            SMCConnectionError: If the connection is not open.
            SMCWriteError: If the write operation fails.
        """
        if not self._is_open:
            raise SMCConnectionError("SMC connection is not open")
        self._call_write_key(key, data, data_type)

    # -- Internal IOKit calls ----------------------------------------------

    def _call_read_key(self, key: str) -> tuple[bytes, str]:
        """Execute the IOKit read for a single SMC key.

        Args:
            key: 4-character SMC key.

        Returns:
            Tuple of (raw_bytes, data_type_string).

        Raises:
            SMCKeyNotFoundError: If the key does not exist.
            SMCReadError: If the IOKit call fails.
        """
        input_struct = _SMCKeyData()
        output_struct = _SMCKeyData()

        input_struct.key = _str_to_uint32(key)
        input_struct.data8 = SMC_CMD_READ_KEYINFO

        kr = IOConnectCallStructMethod(
            self._connection,
            KERNEL_INDEX_SMC,
            input_struct,
            output_struct,
        )
        if kr != _KERN_SUCCESS:
            raise SMCKeyNotFoundError(f"Key not found: {key}")

        data_type = _uint32_to_str(output_struct.keyInfo.dataType)
        data_size = output_struct.keyInfo.dataSize

        if data_size == 0:
            raise SMCKeyNotFoundError(f"Key not found: {key}")

        input_struct2 = _SMCKeyData()
        output_struct2 = _SMCKeyData()
        input_struct2.key = _str_to_uint32(key)
        input_struct2.keyInfo.dataSize = data_size
        input_struct2.data8 = SMC_CMD_READ_BYTES

        kr = IOConnectCallStructMethod(
            self._connection,
            KERNEL_INDEX_SMC,
            input_struct2,
            output_struct2,
        )
        if kr != _KERN_SUCCESS:
            raise SMCReadError(f"Failed to read key: {key}")

        raw = bytes(output_struct2.bytes[:data_size])
        return raw, data_type

    def _call_write_key(
            self, key: str, data: bytes, data_type: str
    ) -> None:
        """Execute the IOKit write for a single SMC key.

        Args:
            key: 4-character SMC key.
            data: Raw bytes to write.
            data_type: SMC data type string.

        Raises:
            SMCWriteError: If the IOKit call fails.
        """
        input_struct = _SMCKeyData()
        input_struct.key = _str_to_uint32(key)
        input_struct.data8 = SMC_CMD_WRITE_BYTES
        input_struct.keyInfo.dataSize = len(data)
        input_struct.keyInfo.dataType = _str_to_uint32(data_type[:4])

        for i, b in enumerate(data):
            input_struct.bytes[i] = b

        output_struct = _SMCKeyData()
        kr = IOConnectCallStructMethod(
            self._connection,
            KERNEL_INDEX_SMC,
            input_struct,
            output_struct,
        )
        if kr != _KERN_SUCCESS:
            raise SMCWriteError(f"Failed to write key: {key}")

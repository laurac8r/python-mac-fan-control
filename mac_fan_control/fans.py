"""Fan discovery, status reading, and speed control via SMC.

Provides ``FanService`` which reads fan status and sets fan speeds through
the Apple SMC interface.
"""

import struct

from mac_fan_control.exceptions import (
    FanNotFoundError,
    SMCKeyNotFoundError,
    SMCWriteVerificationError,
)
from mac_fan_control.models import FanControlMode, FanStatus
from mac_fan_control.smc import SMCConnection, encode_flt, encode_fpe2

_MODE_AUTO = 0
_MODE_FORCED = 1


class FanService:
    """High-level service for fan management.

    Args:
        smc: An open ``SMCConnection`` (or compatible mock).
    """

    def __init__(self, smc: SMCConnection, verify_writes: bool = False) -> None:
        self._smc = smc
        self._verify_writes = verify_writes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fan_count(self) -> int:
        """Return the number of fans detected by the SMC.

        Returns:
            Integer fan count (0 if no fans present).
        """
        return self._smc.read_key_int("FNum")

    def read_fan(self, index: int) -> FanStatus:
        """Read the current status of a single fan.

        Args:
            index: 0-based fan index.

        Returns:
            A populated ``FanStatus`` instance.

        Raises:
            FanNotFoundError: If the index is out of range.
        """
        self._validate_index(index)

        prefix = f"F{index}"
        current_rpm = self._smc.read_key_float(f"{prefix}Ac")
        min_rpm = self._smc.read_key_float(f"{prefix}Mn")
        max_rpm = self._smc.read_key_float(f"{prefix}Mx")
        target_rpm = self._smc.read_key_float(f"{prefix}Tg")
        try:
            mode_byte = self._smc.read_key_int(f"{prefix}Md")
        except (SMCKeyNotFoundError, Exception):
            mode_byte = _MODE_AUTO

        if mode_byte == _MODE_FORCED:
            mode = FanControlMode.CONSTANT
        else:
            mode = FanControlMode.AUTO

        return FanStatus(
            index=index,
            name=f"Fan {index}",
            current_rpm=current_rpm,
            min_rpm=min_rpm,
            max_rpm=max_rpm,
            target_rpm=target_rpm,
            mode=mode,
        )

    def list_fans(self) -> list[FanStatus]:
        """Read the status of all fans.

        Returns:
            List of ``FanStatus`` for each detected fan.
        """
        count = self.fan_count()
        return [self.read_fan(i) for i in range(count)]

    def set_fan_speed(self, index: int, rpm: float) -> None:
        """Set a fan to a constant RPM value.

        The RPM is clamped to the fan's min/max range.

        Args:
            index: 0-based fan index.
            rpm: Desired RPM value.

        Raises:
            FanNotFoundError: If the index is out of range.
        """
        self._validate_index(index)

        fan = self.read_fan(index)
        clamped = max(fan.min_rpm, min(rpm, fan.max_rpm))

        prefix = f"F{index}"
        mn_key = f"{prefix}Mn"
        tg_key = f"{prefix}Tg"
        encoded_mn, dtype_mn = self._encode_fan_float(mn_key, clamped)
        self._smc.write_key(mn_key, encoded_mn, dtype_mn)
        if self._verify_writes:
            self._verify_write(mn_key, clamped)
        try:
            encoded_tg, dtype_tg = self._encode_fan_float(tg_key, clamped)
            self._smc.write_key(tg_key, encoded_tg, dtype_tg)
        except (SMCKeyNotFoundError, Exception):
            pass
        try:
            self._smc.write_key(
                f"{prefix}Md", struct.pack(">B", _MODE_FORCED), "ui8 "
            )
        except (SMCKeyNotFoundError, Exception):
            pass

    def reset_fan_auto(self, index: int) -> None:
        """Reset a fan to automatic (system-controlled) mode.

        Args:
            index: 0-based fan index.

        Raises:
            FanNotFoundError: If the index is out of range.
        """
        self._validate_index(index)
        prefix = f"F{index}"
        mn_key = f"{prefix}Mn"
        tg_key = f"{prefix}Tg"
        encoded_mn, dtype_mn = self._encode_fan_float(mn_key, 0.0)
        self._smc.write_key(mn_key, encoded_mn, dtype_mn)
        try:
            encoded_tg, dtype_tg = self._encode_fan_float(tg_key, 0.0)
            self._smc.write_key(tg_key, encoded_tg, dtype_tg)
        except (SMCKeyNotFoundError, Exception):
            pass
        try:
            self._smc.write_key(
                f"{prefix}Md", struct.pack(">B", _MODE_AUTO), "ui8 "
            )
        except (SMCKeyNotFoundError, Exception):
            pass

    def reset_all_auto(self) -> None:
        """Reset all fans to automatic mode."""
        count = self.fan_count()
        for i in range(count):
            self.reset_fan_auto(i)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _verify_write(self, key: str, expected: float, tolerance: float = 1.0) -> None:
        """Read back a key and raise if the value didn't change.

        Args:
            key: SMC key that was just written.
            expected: The value that should have been written.
            tolerance: Acceptable difference in float comparison.

        Raises:
            SMCWriteVerificationError: If the read-back value doesn't
                match the expected value.
        """
        actual = self._smc.read_key_float(key)
        if abs(actual - expected) > tolerance:
            raise SMCWriteVerificationError(
                f"Write to {key} was silently ignored "
                f"(wrote {expected:.0f}, read back {actual:.0f}). "
                f"On Apple Silicon, fan control requires a signed "
                f"privileged helper. Use Macs Fan Control.app for "
                f"fan speed changes."
            )

    def _get_key_type(self, key: str) -> str:
        """Read an SMC key and return its data type string.

        Args:
            key: 4-character SMC key.

        Returns:
            Data type string, e.g. ``"fpe2"`` or ``"flt "``.
        """
        _, dtype = self._smc.read_key(key)
        return dtype

    def _encode_fan_float(self, key: str, value: float) -> tuple[bytes, str]:
        """Encode a float using the key's native data type.

        Args:
            key: 4-character SMC key to discover the type from.
            value: Float value to encode.

        Returns:
            Tuple of (encoded_bytes, data_type_string).
        """
        dtype = self._get_key_type(key)
        dtype_stripped = dtype.strip()
        if dtype_stripped == "flt":
            return encode_flt(value), dtype
        return encode_fpe2(value), dtype

    def _validate_index(self, index: int) -> None:
        """Raise FanNotFoundError if index is out of range.

        Args:
            index: Fan index to validate.

        Raises:
            FanNotFoundError: If index < 0 or >= fan_count().
        """
        if index < 0:
            raise FanNotFoundError(f"Invalid fan index {index}")
        count = self.fan_count()
        if index >= count:
            raise FanNotFoundError(
                f"Fan index {index} out of range (0..{count - 1})"
            )

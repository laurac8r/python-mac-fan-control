"""Tests for mac_fan_control.smc — low-level SMC interface."""

import struct
from unittest.mock import MagicMock, patch

import pytest

from mac_fan_control.exceptions import (
    SMCConnectionError,
    SMCKeyNotFoundError,
    SMCReadError,
)
from mac_fan_control.smc import (
    SMCConnection,
    decode_fpe2,
    decode_sp78,
    decode_flt,
    decode_ui8,
    decode_ui16,
    decode_ui32,
    encode_flt,
    encode_fpe2,
    encode_sp78,
)


# ---------------------------------------------------------------------------
# Codec unit tests — pure functions, no hardware needed
# ---------------------------------------------------------------------------


class TestDecodeFpe2:
    """fpe2: unsigned 14.2 fixed-point, big-endian."""

    def test_zero(self) -> None:
        assert decode_fpe2(struct.pack(">H", 0)) == pytest.approx(0.0)

    def test_known_value(self) -> None:
        # 2160 RPM → raw = 2160 * 4 = 8640
        raw = struct.pack(">H", 8640)
        assert decode_fpe2(raw) == pytest.approx(2160.0)

    def test_max_value(self) -> None:
        raw = struct.pack(">H", 0xFFFF)
        assert decode_fpe2(raw) == pytest.approx(16383.75)

    def test_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="2 bytes"):
            decode_fpe2(b"\x00")


class TestEncodeFpe2:
    """Encode float → fpe2 bytes."""

    def test_round_trip(self) -> None:
        for value in [0.0, 1200.0, 2160.0, 6156.0]:
            assert decode_fpe2(encode_fpe2(value)) == pytest.approx(value)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            encode_fpe2(-1.0)


class TestDecodeSp78:
    """sp78: signed 8.8 fixed-point, big-endian."""

    def test_zero(self) -> None:
        assert decode_sp78(struct.pack(">h", 0)) == pytest.approx(0.0)

    def test_positive(self) -> None:
        # 52.5 °C → raw = 52.5 * 256 = 13440
        raw = struct.pack(">h", 13440)
        assert decode_sp78(raw) == pytest.approx(52.5)

    def test_negative(self) -> None:
        raw = struct.pack(">h", -2560)  # -10.0
        assert decode_sp78(raw) == pytest.approx(-10.0)

    def test_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="2 bytes"):
            decode_sp78(b"\x00\x00\x00")


class TestEncodeSp78:
    """Encode float → sp78 bytes."""

    def test_round_trip(self) -> None:
        for value in [0.0, 52.5, -10.0, 100.0]:
            assert decode_sp78(encode_sp78(value)) == pytest.approx(value)


class TestDecodeFlt:
    """flt: 4-byte native-endian IEEE 754 float."""

    def test_known_value(self) -> None:
        raw = struct.pack("<f", 48.25)
        assert decode_flt(raw) == pytest.approx(48.25)

    def test_round_trip_various(self) -> None:
        for value in [0.0, 33.0, 72.1875, 2502.0]:
            raw = struct.pack("<f", value)
            assert decode_flt(raw) == pytest.approx(value)

    def test_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="4 bytes"):
            decode_flt(b"\x00\x00")


class TestEncodeFlt:
    """Encode float → flt bytes (native little-endian)."""

    def test_round_trip(self) -> None:
        for value in [0.0, 33.0, 2502.0, 6550.0]:
            assert decode_flt(encode_flt(value)) == pytest.approx(value)

    def test_encode_known_value(self) -> None:
        raw = encode_flt(33.0)
        assert raw == struct.pack("<f", 33.0)


class TestDecodeUi8:
    """ui8: unsigned 8-bit integer."""

    def test_value(self) -> None:
        assert decode_ui8(struct.pack(">B", 2)) == 2

    def test_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="1 byte"):
            decode_ui8(b"\x00\x00")


class TestDecodeUi16:
    """ui16: unsigned 16-bit integer, big-endian."""

    def test_value(self) -> None:
        assert decode_ui16(struct.pack(">H", 1024)) == 1024

    def test_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="2 bytes"):
            decode_ui16(b"\x00")


class TestDecodeUi32:
    """ui32: unsigned 32-bit integer, big-endian."""

    def test_value(self) -> None:
        assert decode_ui32(struct.pack(">I", 120)) == 120

    def test_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="4 bytes"):
            decode_ui32(b"\x00\x00")


# ---------------------------------------------------------------------------
# SMCConnection tests — IOKit calls are mocked
# ---------------------------------------------------------------------------


class TestSMCConnectionOpen:
    """Tests for opening / closing the SMC connection."""

    @patch("mac_fan_control.smc.IOServiceGetMatchingService")
    @patch("mac_fan_control.smc.IOServiceOpen")
    @patch("mac_fan_control.smc.IOServiceMatching")
    def test_open_success(
        self,
        mock_matching: MagicMock,
        mock_open: MagicMock,
        mock_get: MagicMock,
    ) -> None:
        mock_matching.return_value = "match_dict"
        mock_get.return_value = 42  # non-zero = found
        mock_open.return_value = (0, 99)  # kern_return_t 0 = success, conn 99

        conn = SMCConnection()
        conn.open()
        assert conn.is_open

    @patch("mac_fan_control.smc.IOServiceGetMatchingService")
    @patch("mac_fan_control.smc.IOServiceMatching")
    def test_open_service_not_found_raises(
        self,
        mock_matching: MagicMock,
        mock_get: MagicMock,
    ) -> None:
        mock_matching.return_value = "match_dict"
        mock_get.return_value = 0  # 0 = not found

        conn = SMCConnection()
        with pytest.raises(SMCConnectionError, match="AppleSMC"):
            conn.open()

    @patch("mac_fan_control.smc.IOServiceGetMatchingService")
    @patch("mac_fan_control.smc.IOServiceOpen")
    @patch("mac_fan_control.smc.IOServiceMatching")
    def test_context_manager(
        self,
        mock_matching: MagicMock,
        mock_open: MagicMock,
        mock_get: MagicMock,
    ) -> None:
        mock_matching.return_value = "match_dict"
        mock_get.return_value = 42
        mock_open.return_value = (0, 99)

        with SMCConnection() as conn:
            assert conn.is_open
        assert not conn.is_open


class TestSMCConnectionRead:
    """Tests for reading SMC keys (IOKit calls mocked)."""

    def _make_open_conn(self) -> SMCConnection:
        """Return an SMCConnection with internals faked as open."""
        conn = SMCConnection()
        conn._connection = 99
        conn._is_open = True
        return conn

    @patch("mac_fan_control.smc.SMCConnection._call_read_key")
    def test_read_key_returns_bytes_and_type(
        self, mock_call: MagicMock
    ) -> None:
        mock_call.return_value = (struct.pack(">H", 8640), "fpe2")
        conn = self._make_open_conn()
        raw, dtype = conn.read_key("F0Ac")
        assert dtype == "fpe2"
        assert decode_fpe2(raw) == pytest.approx(2160.0)

    @patch("mac_fan_control.smc.SMCConnection._call_read_key")
    def test_read_key_not_found(self, mock_call: MagicMock) -> None:
        mock_call.side_effect = SMCKeyNotFoundError("XXXX")
        conn = self._make_open_conn()
        with pytest.raises(SMCKeyNotFoundError):
            conn.read_key("XXXX")

    def test_read_key_when_closed_raises(self) -> None:
        conn = SMCConnection()
        with pytest.raises(SMCConnectionError, match="not open"):
            conn.read_key("F0Ac")


class TestSMCConnectionReadDecoded:
    """Tests for the convenience read_key_decoded method."""

    def _make_open_conn(self) -> SMCConnection:
        conn = SMCConnection()
        conn._connection = 99
        conn._is_open = True
        return conn

    @patch("mac_fan_control.smc.SMCConnection._call_read_key")
    def test_read_float_fpe2(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (struct.pack(">H", 8640), "fpe2")
        conn = self._make_open_conn()
        assert conn.read_key_float("F0Ac") == pytest.approx(2160.0)

    @patch("mac_fan_control.smc.SMCConnection._call_read_key")
    def test_read_float_sp78(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (struct.pack(">h", 13440), "sp78")
        conn = self._make_open_conn()
        assert conn.read_key_float("TC0P") == pytest.approx(52.5)

    @patch("mac_fan_control.smc.SMCConnection._call_read_key")
    def test_read_float_flt(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (struct.pack("<f", 48.25), "flt ")
        conn = self._make_open_conn()
        assert conn.read_key_float("TG0P") == pytest.approx(48.25)

    @patch("mac_fan_control.smc.SMCConnection._call_read_key")
    def test_read_int(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (struct.pack(">B", 2), "ui8 ")
        conn = self._make_open_conn()
        assert conn.read_key_int("FNum") == 2


class TestSMCConnectionNullKey:
    """Tests for keys that return null dataType/dataSize."""

    def _make_open_conn(self) -> SMCConnection:
        conn = SMCConnection()
        conn._connection = 99
        conn._is_open = True
        return conn

    @patch("mac_fan_control.smc.SMCConnection._call_read_key")
    def test_null_type_raises_key_not_found(self, mock_call: MagicMock) -> None:
        """SMC keys with zero dataType/dataSize should raise SMCKeyNotFoundError."""
        mock_call.side_effect = SMCKeyNotFoundError("Key not found: F0Md")
        conn = self._make_open_conn()
        with pytest.raises(SMCKeyNotFoundError):
            conn.read_key("F0Md")

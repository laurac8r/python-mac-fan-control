"""Tests for mac_fan_control.fans — fan discovery, status, and speed control."""

import struct
from unittest.mock import MagicMock, call

import pytest

from mac_fan_control.exceptions import FanNotFoundError, SMCWriteVerificationError
from mac_fan_control.fans import FanService
from mac_fan_control.models import FanControlMode, FanStatus
from mac_fan_control.smc import decode_flt, decode_fpe2, encode_fpe2


@pytest.fixture()
def fan_service(mock_smc_connection: MagicMock) -> FanService:
    """Return a FanService wired to the mock SMC connection."""
    return FanService(smc=mock_smc_connection)


class TestFanServiceFanCount:
    """Tests for reading the number of fans."""

    def test_fan_count(self, fan_service: FanService) -> None:
        assert fan_service.fan_count() == 2

    def test_fan_count_zero(
        self,
        mock_smc_connection: MagicMock,
        smc_values: dict[str, tuple[bytes, str]],
    ) -> None:
        smc_values["FNum"] = (struct.pack(">B", 0), "ui8 ")
        service = FanService(smc=mock_smc_connection)
        assert service.fan_count() == 0


class TestFanServiceReadFan:
    """Tests for reading a single fan's status."""

    def test_read_fan_0(self, fan_service: FanService) -> None:
        fan = fan_service.read_fan(0)
        assert isinstance(fan, FanStatus)
        assert fan.index == 0
        assert fan.current_rpm == pytest.approx(2160.0)
        assert fan.min_rpm == pytest.approx(1200.0)
        assert fan.max_rpm == pytest.approx(6156.0)
        assert fan.mode == FanControlMode.AUTO

    def test_read_fan_1(self, fan_service: FanService) -> None:
        fan = fan_service.read_fan(1)
        assert fan.index == 1
        assert fan.current_rpm == pytest.approx(2000.0)
        assert fan.min_rpm == pytest.approx(1200.0)
        assert fan.max_rpm == pytest.approx(5900.0)

    def test_read_fan_out_of_range_raises(
        self, fan_service: FanService
    ) -> None:
        with pytest.raises(FanNotFoundError, match="index 5"):
            fan_service.read_fan(5)

    def test_read_fan_negative_raises(
        self, fan_service: FanService
    ) -> None:
        with pytest.raises(FanNotFoundError):
            fan_service.read_fan(-1)

    def test_fan_mode_forced(
        self,
        mock_smc_connection: MagicMock,
        smc_values: dict[str, tuple[bytes, str]],
    ) -> None:
        """Mode byte 1 = forced/constant."""
        smc_values["F0Md"] = (struct.pack(">B", 1), "ui8 ")
        smc_values["F0Tg"] = (
            struct.pack(">H", int(3000.0 * 4)),
            "fpe2",
        )
        service = FanService(smc=mock_smc_connection)
        fan = service.read_fan(0)
        assert fan.mode == FanControlMode.CONSTANT
        assert fan.target_rpm == pytest.approx(3000.0)

    def test_missing_mode_key_defaults_to_auto(
        self,
        mock_smc_connection: MagicMock,
        smc_values: dict[str, tuple[bytes, str]],
    ) -> None:
        """On Apple Silicon, F0Md may not exist — should default to AUTO."""
        smc_values.pop("F0Md", None)
        service = FanService(smc=mock_smc_connection)
        fan = service.read_fan(0)
        assert fan.mode == FanControlMode.AUTO


class TestFanServiceListFans:
    """Tests for listing all fans."""

    def test_list_all_fans(self, fan_service: FanService) -> None:
        fans = fan_service.list_fans()
        assert len(fans) == 2
        assert fans[0].index == 0
        assert fans[1].index == 1

    def test_list_fans_returns_fan_status(
        self, fan_service: FanService
    ) -> None:
        for fan in fan_service.list_fans():
            assert isinstance(fan, FanStatus)

    def test_list_fans_zero_fans(
        self,
        mock_smc_connection: MagicMock,
        smc_values: dict[str, tuple[bytes, str]],
    ) -> None:
        smc_values["FNum"] = (struct.pack(">B", 0), "ui8 ")
        service = FanService(smc=mock_smc_connection)
        assert service.list_fans() == []


class TestFanServiceSetSpeed:
    """Tests for setting fan speed."""

    def test_set_constant_speed_writes_min_and_target(
        self,
        fan_service: FanService,
        mock_smc_connection: MagicMock,
    ) -> None:
        """Setting speed should write both F0Mn and F0Tg."""
        fan_service.set_fan_speed(0, 3000.0)
        mock_smc_connection.write_key.assert_called()
        calls = mock_smc_connection.write_key.call_args_list
        keys_written = {c.args[0] for c in calls}
        assert "F0Mn" in keys_written
        assert "F0Tg" in keys_written

    def test_set_speed_out_of_range_raises(
        self, fan_service: FanService
    ) -> None:
        with pytest.raises(FanNotFoundError):
            fan_service.set_fan_speed(5, 3000.0)

    def test_set_speed_clamped_to_min(
        self,
        fan_service: FanService,
        mock_smc_connection: MagicMock,
    ) -> None:
        """Speed below min_rpm should be clamped to min_rpm."""
        fan_service.set_fan_speed(0, 100.0)
        mn_call = [
            c for c in mock_smc_connection.write_key.call_args_list
            if c.args[0] == "F0Mn"
        ][0]
        assert decode_fpe2(mn_call.args[1]) == pytest.approx(1200.0)

    def test_set_speed_clamped_to_max(
        self,
        fan_service: FanService,
        mock_smc_connection: MagicMock,
    ) -> None:
        """Speed above max_rpm should be clamped to max_rpm."""
        fan_service.set_fan_speed(0, 99999.0)
        mn_call = [
            c for c in mock_smc_connection.write_key.call_args_list
            if c.args[0] == "F0Mn"
        ][0]
        assert decode_fpe2(mn_call.args[1]) == pytest.approx(6156.0)

    def test_set_speed_uses_flt_when_key_is_flt(
        self,
        mock_smc_connection: MagicMock,
        smc_values: dict[str, tuple[bytes, str]],
    ) -> None:
        """On Apple Silicon, F0Mn uses flt type — writes must match."""
        from tests.conftest import make_flt_bytes
        smc_values["F0Ac"] = (make_flt_bytes(2500.0), "flt ")
        smc_values["F0Mn"] = (make_flt_bytes(2317.0), "flt ")
        smc_values["F0Mx"] = (make_flt_bytes(6550.0), "flt ")
        smc_values["F0Tg"] = (make_flt_bytes(0.0), "flt ")
        service = FanService(smc=mock_smc_connection)
        service.set_fan_speed(0, 4000.0)
        mn_call = [
            c for c in mock_smc_connection.write_key.call_args_list
            if c.args[0] == "F0Mn"
        ][0]
        assert mn_call.args[2] == "flt "
        assert decode_flt(mn_call.args[1]) == pytest.approx(4000.0)

    def test_set_speed_raises_on_silent_write_failure(
        self,
        mock_smc_connection: MagicMock,
        smc_values: dict[str, tuple[bytes, str]],
    ) -> None:
        """When SMC accepts write but value doesn't change, raise."""
        # Make write_key a no-op (value in smc_values stays the same)
        # but read_key_float still returns the old value
        service = FanService(smc=mock_smc_connection, verify_writes=True)
        with pytest.raises(SMCWriteVerificationError, match="F0Mn"):
            service.set_fan_speed(0, 3000.0)


class TestFanServiceResetAuto:
    """Tests for resetting a fan to automatic control."""

    def test_reset_to_auto_writes_min(
        self,
        fan_service: FanService,
        mock_smc_connection: MagicMock,
    ) -> None:
        """Reset should restore F0Mn to 0 to let the system decide."""
        fan_service.reset_fan_auto(0)
        calls = mock_smc_connection.write_key.call_args_list
        keys_written = {c.args[0] for c in calls}
        assert "F0Mn" in keys_written

    def test_reset_auto_out_of_range_raises(
        self, fan_service: FanService
    ) -> None:
        with pytest.raises(FanNotFoundError):
            fan_service.reset_fan_auto(5)

    def test_reset_all_fans(
        self,
        fan_service: FanService,
        mock_smc_connection: MagicMock,
    ) -> None:
        fan_service.reset_all_auto()
        calls = mock_smc_connection.write_key.call_args_list
        keys_written = [c.args[0] for c in calls]
        assert "F0Mn" in keys_written
        assert "F1Mn" in keys_written

"""Tests for mac_fan_control.sensors — temperature sensor discovery & reading."""

import struct
from unittest.mock import MagicMock, patch

import pytest

from mac_fan_control.exceptions import SensorNotFoundError, SMCKeyNotFoundError
from mac_fan_control.models import TemperatureSensor
from mac_fan_control.sensors import (
    KNOWN_SENSOR_NAMES,
    SensorService,
)


@pytest.fixture()
def sensor_service(mock_smc_connection: MagicMock) -> SensorService:
    """Return a SensorService wired to the mock SMC connection."""
    return SensorService(smc=mock_smc_connection)


class TestKnownSensorNames:
    """Verify the built-in sensor name mapping is populated."""

    def test_contains_cpu_proximity(self) -> None:
        assert "TC0P" in KNOWN_SENSOR_NAMES

    def test_contains_gpu(self) -> None:
        assert "TG0P" in KNOWN_SENSOR_NAMES

    def test_contains_battery(self) -> None:
        assert "TB0T" in KNOWN_SENSOR_NAMES

    def test_contains_apple_silicon_cpu(self) -> None:
        assert "Tp0C" in KNOWN_SENSOR_NAMES

    def test_contains_apple_silicon_soc(self) -> None:
        assert "Tp0a" in KNOWN_SENSOR_NAMES

    def test_values_are_strings(self) -> None:
        for key, name in KNOWN_SENSOR_NAMES.items():
            assert isinstance(key, str)
            assert isinstance(name, str)


class TestSensorServiceReadSensor:
    """Tests for reading a single sensor by key."""

    def test_read_known_sensor(self, sensor_service: SensorService) -> None:
        sensor = sensor_service.read_sensor("TC0P")
        assert isinstance(sensor, TemperatureSensor)
        assert sensor.key == "TC0P"
        assert sensor.temperature_c == pytest.approx(52.5)
        assert sensor.name == KNOWN_SENSOR_NAMES["TC0P"]

    def test_read_unknown_key_raises(
        self, sensor_service: SensorService
    ) -> None:
        with pytest.raises(SensorNotFoundError, match="XXXX"):
            sensor_service.read_sensor("XXXX")

    def test_read_sensor_with_custom_name(
        self,
        mock_smc_connection: MagicMock,
        smc_values: dict[str, tuple[bytes, str]],
    ) -> None:
        service = SensorService(smc=mock_smc_connection)
        sensor = service.read_sensor("TC0P")
        assert sensor.name == KNOWN_SENSOR_NAMES["TC0P"]

    def test_read_sensor_unknown_name_falls_back(
        self,
        mock_smc_connection: MagicMock,
        smc_values: dict[str, tuple[bytes, str]],
    ) -> None:
        """Sensor key not in KNOWN_SENSOR_NAMES gets the key as its name."""
        smc_values["Tz0Q"] = (
            struct.pack(">h", int(30.0 * 256)),
            "sp78",
        )
        service = SensorService(smc=mock_smc_connection)
        sensor = service.read_sensor("Tz0Q")
        assert sensor.name == "Tz0Q"
        assert sensor.temperature_c == pytest.approx(30.0)


class TestSensorServiceListSensors:
    """Tests for discovering all available sensors."""

    def test_list_returns_known_sensors(
        self, sensor_service: SensorService
    ) -> None:
        sensors = sensor_service.list_sensors()
        keys = {s.key for s in sensors}
        assert "TC0P" in keys
        assert "TG0P" in keys
        assert "TB0T" in keys

    def test_list_skips_missing_keys(
        self,
        mock_smc_connection: MagicMock,
        smc_values: dict[str, tuple[bytes, str]],
    ) -> None:
        """Sensors whose keys don't exist on this machine are skipped."""
        smc_values.pop("TG0P", None)
        service = SensorService(smc=mock_smc_connection)
        sensors = service.list_sensors()
        keys = {s.key for s in sensors}
        assert "TG0P" not in keys

    def test_list_returns_temperature_sensor_objects(
        self, sensor_service: SensorService
    ) -> None:
        sensors = sensor_service.list_sensors()
        for s in sensors:
            assert isinstance(s, TemperatureSensor)

    def test_list_sensors_all_have_names(
        self, sensor_service: SensorService
    ) -> None:
        sensors = sensor_service.list_sensors()
        for s in sensors:
            assert len(s.name) > 0


class TestSensorServiceProbeKeys:
    """Tests for probing arbitrary SMC keys for temperature data."""

    def test_probe_returns_only_valid_temps(
        self,
        mock_smc_connection: MagicMock,
        smc_values: dict[str, tuple[bytes, str]],
    ) -> None:
        """Probing should return sensors whose temps are in a sane range."""
        service = SensorService(smc=mock_smc_connection)
        sensors = service.probe_keys(["TC0P", "XXXX", "TB0T"])
        keys = {s.key for s in sensors}
        assert "TC0P" in keys
        assert "TB0T" in keys
        assert "XXXX" not in keys

    def test_probe_filters_out_of_range_temps(
        self,
        mock_smc_connection: MagicMock,
        smc_values: dict[str, tuple[bytes, str]],
    ) -> None:
        """Temperatures outside -40..200 °C should be excluded."""
        smc_values["Tz99"] = (
            struct.pack("<f", 250.0),
            "flt ",
        )
        service = SensorService(smc=mock_smc_connection)
        sensors = service.probe_keys(["Tz99"])
        assert len(sensors) == 0

"""Tests for mac_fan_control.models — Pydantic data models."""

import pytest
from pydantic import ValidationError

from mac_fan_control.models import (
    FanControlMode,
    FanProfile,
    FanStatus,
    TemperatureSensor,
    TemperatureUnit,
)


class TestTemperatureSensor:
    """Tests for the TemperatureSensor model."""

    def test_create_sensor_celsius(self) -> None:
        sensor = TemperatureSensor(
            key="TC0P",
            name="CPU Proximity",
            temperature_c=52.5,
        )
        assert sensor.key == "TC0P"
        assert sensor.name == "CPU Proximity"
        assert sensor.temperature_c == 52.5

    def test_temperature_fahrenheit(self) -> None:
        sensor = TemperatureSensor(
            key="TC0P",
            name="CPU Proximity",
            temperature_c=100.0,
        )
        assert sensor.temperature_f == pytest.approx(212.0)

    def test_temperature_fahrenheit_freezing(self) -> None:
        sensor = TemperatureSensor(
            key="TB0T",
            name="Battery",
            temperature_c=0.0,
        )
        assert sensor.temperature_f == pytest.approx(32.0)

    def test_display_string_celsius(self) -> None:
        sensor = TemperatureSensor(
            key="TC0P",
            name="CPU Proximity",
            temperature_c=52.5,
        )
        result = sensor.display(unit=TemperatureUnit.CELSIUS, precise=True)
        assert "52.5" in result
        assert "°C" in result

    def test_display_string_fahrenheit(self) -> None:
        sensor = TemperatureSensor(
            key="TC0P",
            name="CPU Proximity",
            temperature_c=52.5,
        )
        result = sensor.display(unit=TemperatureUnit.FAHRENHEIT, precise=False)
        assert "°F" in result

    def test_display_rounded_when_not_precise(self) -> None:
        sensor = TemperatureSensor(
            key="TC0P",
            name="CPU Proximity",
            temperature_c=52.7,
        )
        result = sensor.display(unit=TemperatureUnit.CELSIUS, precise=False)
        assert "53" in result
        assert "52.7" not in result


class TestFanStatus:
    """Tests for the FanStatus model."""

    def test_create_fan_status(self) -> None:
        fan = FanStatus(
            index=0,
            name="Left Fan",
            current_rpm=2160.0,
            min_rpm=1200.0,
            max_rpm=6156.0,
            target_rpm=0.0,
            mode=FanControlMode.AUTO,
        )
        assert fan.index == 0
        assert fan.current_rpm == 2160.0
        assert fan.mode == FanControlMode.AUTO

    def test_fan_percentage(self) -> None:
        fan = FanStatus(
            index=0,
            name="Fan",
            current_rpm=3678.0,
            min_rpm=1200.0,
            max_rpm=6156.0,
            target_rpm=0.0,
            mode=FanControlMode.AUTO,
        )
        expected = (3678.0 - 1200.0) / (6156.0 - 1200.0) * 100
        assert fan.percentage == pytest.approx(expected)

    def test_fan_percentage_at_min(self) -> None:
        fan = FanStatus(
            index=0,
            name="Fan",
            current_rpm=1200.0,
            min_rpm=1200.0,
            max_rpm=6156.0,
            target_rpm=0.0,
            mode=FanControlMode.AUTO,
        )
        assert fan.percentage == pytest.approx(0.0)

    def test_fan_percentage_equal_min_max(self) -> None:
        fan = FanStatus(
            index=0,
            name="Fan",
            current_rpm=1200.0,
            min_rpm=1200.0,
            max_rpm=1200.0,
            target_rpm=0.0,
            mode=FanControlMode.AUTO,
        )
        assert fan.percentage == pytest.approx(0.0)

    def test_negative_rpm_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FanStatus(
                index=0,
                name="Fan",
                current_rpm=-1.0,
                min_rpm=1200.0,
                max_rpm=6156.0,
                target_rpm=0.0,
                mode=FanControlMode.AUTO,
            )

    def test_negative_index_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FanStatus(
                index=-1,
                name="Fan",
                current_rpm=2000.0,
                min_rpm=1200.0,
                max_rpm=6156.0,
                target_rpm=0.0,
                mode=FanControlMode.AUTO,
            )


class TestFanProfile:
    """Tests for the FanProfile model."""

    def test_auto_profile(self) -> None:
        profile = FanProfile(fan_index=0, mode=FanControlMode.AUTO)
        assert profile.mode == FanControlMode.AUTO
        assert profile.constant_rpm is None
        assert profile.sensor_key is None

    def test_constant_profile(self) -> None:
        profile = FanProfile(
            fan_index=0,
            mode=FanControlMode.CONSTANT,
            constant_rpm=3000.0,
        )
        assert profile.constant_rpm == 3000.0

    def test_sensor_based_profile(self) -> None:
        profile = FanProfile(
            fan_index=0,
            mode=FanControlMode.SENSOR_BASED,
            sensor_key="TC0P",
            temp_low_c=40.0,
            temp_high_c=80.0,
        )
        assert profile.sensor_key == "TC0P"
        assert profile.temp_low_c == 40.0
        assert profile.temp_high_c == 80.0

    def test_constant_profile_requires_rpm(self) -> None:
        with pytest.raises(ValidationError, match="constant_rpm"):
            FanProfile(fan_index=0, mode=FanControlMode.CONSTANT)

    def test_sensor_profile_requires_sensor_key(self) -> None:
        with pytest.raises(ValidationError, match="sensor_key"):
            FanProfile(
                fan_index=0,
                mode=FanControlMode.SENSOR_BASED,
                temp_low_c=40.0,
                temp_high_c=80.0,
            )


class TestFanControlMode:
    """Tests for the FanControlMode enum."""

    def test_auto_value(self) -> None:
        assert FanControlMode.AUTO.value == "auto"

    def test_constant_value(self) -> None:
        assert FanControlMode.CONSTANT.value == "constant"

    def test_sensor_based_value(self) -> None:
        assert FanControlMode.SENSOR_BASED.value == "sensor_based"

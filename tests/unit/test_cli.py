"""Tests for mac_fan_control.cli — Click CLI interface."""

import struct
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mac_fan_control.cli import main
from mac_fan_control.exceptions import SMCWriteVerificationError
from mac_fan_control.models import FanControlMode, FanStatus, TemperatureSensor


@pytest.fixture()
def runner() -> CliRunner:
    """Return a Click test runner."""
    return CliRunner()


@pytest.fixture()
def mock_sensors() -> list[TemperatureSensor]:
    """Return a sample list of temperature sensors."""
    return [
        TemperatureSensor(key="TC0P", name="CPU Proximity", temperature_c=52.5),
        TemperatureSensor(key="TG0P", name="GPU Proximity", temperature_c=48.25),
        TemperatureSensor(key="TB0T", name="Battery TS_MAX", temperature_c=33.5),
    ]


@pytest.fixture()
def mock_fans() -> list[FanStatus]:
    """Return a sample list of fan statuses."""
    return [
        FanStatus(
            index=0,
            name="Fan 0",
            current_rpm=2160.0,
            min_rpm=1200.0,
            max_rpm=6156.0,
            target_rpm=0.0,
            mode=FanControlMode.AUTO,
        ),
        FanStatus(
            index=1,
            name="Fan 1",
            current_rpm=2000.0,
            min_rpm=1200.0,
            max_rpm=5900.0,
            target_rpm=0.0,
            mode=FanControlMode.AUTO,
        ),
    ]


class TestCliStatus:
    """Tests for the 'status' subcommand."""

    @patch("mac_fan_control.cli._create_services")
    def test_status_displays_fans_and_sensors(
        self,
        mock_create: MagicMock,
        runner: CliRunner,
        mock_fans: list[FanStatus],
        mock_sensors: list[TemperatureSensor],
    ) -> None:
        mock_fan_svc = MagicMock()
        mock_sensor_svc = MagicMock()
        mock_fan_svc.list_fans.return_value = mock_fans
        mock_sensor_svc.list_sensors.return_value = mock_sensors
        mock_create.return_value = (mock_fan_svc, mock_sensor_svc)

        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "Fan 0" in result.output
        assert "Fan 1" in result.output
        assert "2160" in result.output
        assert "CPU Proximity" in result.output
        assert "52.5" in result.output or "52" in result.output

    @patch("mac_fan_control.cli._create_services")
    def test_status_fahrenheit(
        self,
        mock_create: MagicMock,
        runner: CliRunner,
        mock_fans: list[FanStatus],
        mock_sensors: list[TemperatureSensor],
    ) -> None:
        mock_fan_svc = MagicMock()
        mock_sensor_svc = MagicMock()
        mock_fan_svc.list_fans.return_value = mock_fans
        mock_sensor_svc.list_sensors.return_value = mock_sensors
        mock_create.return_value = (mock_fan_svc, mock_sensor_svc)

        result = runner.invoke(main, ["status", "--fahrenheit"])
        assert result.exit_code == 0
        assert "°F" in result.output

    @patch("mac_fan_control.cli._create_services")
    def test_status_no_fans(
        self,
        mock_create: MagicMock,
        runner: CliRunner,
        mock_sensors: list[TemperatureSensor],
    ) -> None:
        mock_fan_svc = MagicMock()
        mock_sensor_svc = MagicMock()
        mock_fan_svc.list_fans.return_value = []
        mock_sensor_svc.list_sensors.return_value = mock_sensors
        mock_create.return_value = (mock_fan_svc, mock_sensor_svc)

        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "No fans" in result.output or "no fans" in result.output.lower()


class TestCliFans:
    """Tests for the 'fans' subcommand."""

    @patch("mac_fan_control.cli._create_services")
    def test_fans_list(
        self,
        mock_create: MagicMock,
        runner: CliRunner,
        mock_fans: list[FanStatus],
    ) -> None:
        mock_fan_svc = MagicMock()
        mock_sensor_svc = MagicMock()
        mock_fan_svc.list_fans.return_value = mock_fans
        mock_create.return_value = (mock_fan_svc, mock_sensor_svc)

        result = runner.invoke(main, ["fans"])
        assert result.exit_code == 0
        assert "Fan 0" in result.output
        assert "Fan 1" in result.output
        assert "Auto" in result.output or "auto" in result.output.lower()


class TestCliSensors:
    """Tests for the 'sensors' subcommand."""

    @patch("mac_fan_control.cli._create_services")
    def test_sensors_list(
        self,
        mock_create: MagicMock,
        runner: CliRunner,
        mock_sensors: list[TemperatureSensor],
    ) -> None:
        mock_fan_svc = MagicMock()
        mock_sensor_svc = MagicMock()
        mock_sensor_svc.list_sensors.return_value = mock_sensors
        mock_create.return_value = (mock_fan_svc, mock_sensor_svc)

        result = runner.invoke(main, ["sensors"])
        assert result.exit_code == 0
        assert "CPU Proximity" in result.output
        assert "GPU Proximity" in result.output
        assert "Battery" in result.output


class TestCliSet:
    """Tests for the 'set' subcommand."""

    @patch("mac_fan_control.cli._create_services")
    def test_set_fan_speed(
        self,
        mock_create: MagicMock,
        runner: CliRunner,
    ) -> None:
        mock_fan_svc = MagicMock()
        mock_sensor_svc = MagicMock()
        mock_create.return_value = (mock_fan_svc, mock_sensor_svc)

        result = runner.invoke(main, ["set", "0", "3000"])
        assert result.exit_code == 0
        mock_fan_svc.set_fan_speed.assert_called_once_with(0, 3000.0)

    @patch("mac_fan_control.cli._create_services")
    def test_set_fan_speed_non_integer_index(
        self,
        mock_create: MagicMock,
        runner: CliRunner,
    ) -> None:
        result = runner.invoke(main, ["set", "abc", "3000"])
        assert result.exit_code != 0

    @patch("mac_fan_control.cli._create_services")
    def test_set_fan_speed_write_verification_error(
        self,
        mock_create: MagicMock,
        runner: CliRunner,
    ) -> None:
        """On Apple Silicon, set should show a clear error when writes are ignored."""
        mock_fan_svc = MagicMock()
        mock_sensor_svc = MagicMock()
        mock_fan_svc.set_fan_speed.side_effect = SMCWriteVerificationError(
            "Write to F0Mn was silently ignored"
        )
        mock_create.return_value = (mock_fan_svc, mock_sensor_svc)

        result = runner.invoke(main, ["set", "0", "3000"])
        assert result.exit_code != 0
        assert "silently ignored" in result.output


class TestCliReset:
    """Tests for the 'reset' subcommand."""

    @patch("mac_fan_control.cli._create_services")
    def test_reset_single_fan(
        self,
        mock_create: MagicMock,
        runner: CliRunner,
    ) -> None:
        mock_fan_svc = MagicMock()
        mock_sensor_svc = MagicMock()
        mock_create.return_value = (mock_fan_svc, mock_sensor_svc)

        result = runner.invoke(main, ["reset", "0"])
        assert result.exit_code == 0
        mock_fan_svc.reset_fan_auto.assert_called_once_with(0)

    @patch("mac_fan_control.cli._create_services")
    def test_reset_all_fans(
        self,
        mock_create: MagicMock,
        runner: CliRunner,
    ) -> None:
        mock_fan_svc = MagicMock()
        mock_sensor_svc = MagicMock()
        mock_create.return_value = (mock_fan_svc, mock_sensor_svc)

        result = runner.invoke(main, ["reset", "--all"])
        assert result.exit_code == 0
        mock_fan_svc.reset_all_auto.assert_called_once()


class TestCliHelp:
    """Smoke tests for --help on all commands."""

    def test_main_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "fan" in result.output.lower()

    def test_status_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["status", "--help"])
        assert result.exit_code == 0

    def test_set_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["set", "--help"])
        assert result.exit_code == 0

    def test_reset_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["reset", "--help"])
        assert result.exit_code == 0

"""Click-based CLI for mac_fan_control.

Provides commands to monitor temperature sensors, view fan status,
set fan speeds, and reset fans to automatic control.
"""

from __future__ import annotations

import click

from mac_fan_control.exceptions import SMCWriteVerificationError
from mac_fan_control.fans import FanService
from mac_fan_control.models import FanControlMode, FanStatus, TemperatureSensor, TemperatureUnit
from mac_fan_control.sensors import SensorService
from mac_fan_control.smc import SMCConnection


def _create_services(
    verify_writes: bool = False,
) -> tuple[FanService, SensorService]:
    """Open an SMC connection and return fan/sensor services.

    Args:
        verify_writes: If True, read back after writes and raise on failure.

    Returns:
        Tuple of (FanService, SensorService) backed by a live SMC connection.
    """
    smc = SMCConnection()
    smc.open()
    return FanService(smc=smc, verify_writes=verify_writes), SensorService(smc=smc)


def _format_sensor(
    sensor: TemperatureSensor,
    fahrenheit: bool = False,
    precise: bool = True,
) -> str:
    """Format a sensor for CLI display.

    Args:
        sensor: The temperature sensor to format.
        fahrenheit: If True, display in Fahrenheit.
        precise: If True, show one decimal place.

    Returns:
        Formatted string like "TC0P  CPU Proximity         52.5 °C".
    """
    unit = TemperatureUnit.FAHRENHEIT if fahrenheit else TemperatureUnit.CELSIUS
    temp_str = sensor.display(unit=unit, precise=precise)
    return f"  {sensor.key}  {sensor.name:<28s} {temp_str}"


def _format_fan(fan: FanStatus) -> str:
    """Format a fan status for CLI display.

    Args:
        fan: The fan status to format.

    Returns:
        Formatted string with RPM and mode info.
    """
    mode_str = fan.mode.value.capitalize()
    return (
        f"  {fan.name:<10s}  "
        f"{fan.current_rpm:6.0f} RPM  "
        f"({fan.min_rpm:.0f}/{fan.max_rpm:.0f})  "
        f"[{mode_str}]"
    )


@click.group()
@click.version_option(package_name="mac-fan-control")
def main() -> None:
    """Python Mac Fan Control — monitor sensors and control fan speeds."""


@main.command()
@click.option("--fahrenheit", "-f", is_flag=True, help="Display temperatures in Fahrenheit.")
@click.option("--precise", "-p", is_flag=True, help="Show one decimal place for temperatures.")
def status(fahrenheit: bool, precise: bool) -> None:
    """Show current fan and temperature sensor status."""
    fan_svc, sensor_svc = _create_services()

    fans = fan_svc.list_fans()
    sensors = sensor_svc.list_sensors()

    click.echo("Fans:")
    if not fans:
        click.echo("  No fans detected.")
    else:
        for fan in fans:
            click.echo(_format_fan(fan))

    click.echo()
    click.echo("Temperature Sensors:")
    if not sensors:
        click.echo("  No sensors detected.")
    else:
        for sensor in sensors:
            click.echo(_format_sensor(sensor, fahrenheit=fahrenheit, precise=precise))


@main.command()
def fans() -> None:
    """List all fans and their current status."""
    fan_svc, _ = _create_services()
    fans_list = fan_svc.list_fans()

    if not fans_list:
        click.echo("No fans detected.")
        return

    for fan in fans_list:
        click.echo(_format_fan(fan))


@main.command()
@click.option("--fahrenheit", "-f", is_flag=True, help="Display temperatures in Fahrenheit.")
@click.option("--precise", "-p", is_flag=True, help="Show one decimal place for temperatures.")
def sensors(fahrenheit: bool, precise: bool) -> None:
    """List all temperature sensors."""
    _, sensor_svc = _create_services()
    sensors_list = sensor_svc.list_sensors()

    if not sensors_list:
        click.echo("No sensors detected.")
        return

    for sensor in sensors_list:
        click.echo(_format_sensor(sensor, fahrenheit=fahrenheit, precise=precise))


@main.command("set")
@click.argument("fan_index", type=int)
@click.argument("rpm", type=float)
def set_speed(fan_index: int, rpm: float) -> None:
    """Set a fan to a constant RPM value.

    FAN_INDEX is the 0-based fan number. RPM is the desired speed.
    """
    fan_svc, _ = _create_services(verify_writes=True)
    try:
        fan_svc.set_fan_speed(fan_index, rpm)
    except SMCWriteVerificationError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)
    click.echo(f"Fan {fan_index} set to {rpm:.0f} RPM.")


@main.command()
@click.argument("fan_index", type=int, required=False, default=None)
@click.option("--all", "all_fans", is_flag=True, help="Reset all fans to auto.")
def reset(fan_index: int | None, all_fans: bool) -> None:
    """Reset fan(s) to automatic (system-controlled) mode.

    Provide FAN_INDEX to reset a single fan, or --all for all fans.
    """
    fan_svc, _ = _create_services()

    try:
        if all_fans:
            fan_svc.reset_all_auto()
            click.echo("All fans reset to automatic control.")
        elif fan_index is not None:
            fan_svc.reset_fan_auto(fan_index)
            click.echo(f"Fan {fan_index} reset to automatic control.")
        else:
            click.echo("Specify a fan index or use --all.", err=True)
            raise SystemExit(1)
    except SMCWriteVerificationError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)

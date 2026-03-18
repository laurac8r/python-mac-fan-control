"""Pydantic data models for mac_fan_control."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TemperatureUnit(str, Enum):
    """Temperature display unit."""

    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"


class FanControlMode(str, Enum):
    """Fan control mode."""

    AUTO = "auto"
    CONSTANT = "constant"
    SENSOR_BASED = "sensor_based"


class TemperatureSensor(BaseModel):
    """A temperature sensor reading from SMC or IOKit."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(description="SMC key identifier, e.g. 'TC0P'")
    name: str = Field(description="Human-readable sensor name")
    temperature_c: float = Field(description="Temperature in Celsius")

    @property
    def temperature_f(self) -> float:
        """Return the temperature converted to Fahrenheit."""
        return self.temperature_c * 9.0 / 5.0 + 32.0

    def display(
        self,
        unit: TemperatureUnit = TemperatureUnit.CELSIUS,
        precise: bool = False,
    ) -> str:
        """Return a formatted display string.

        Args:
            unit: Temperature unit to display.
            precise: If True, show one decimal place; otherwise round.

        Returns:
            Formatted temperature string, e.g. "52.5 °C" or "53 °C".
        """
        if unit == TemperatureUnit.FAHRENHEIT:
            value = self.temperature_f
            suffix = "°F"
        else:
            value = self.temperature_c
            suffix = "°C"

        if precise:
            return f"{value:.1f} {suffix}"
        return f"{round(value)} {suffix}"


class FanStatus(BaseModel):
    """Current status of a single fan."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0, description="Fan index (0-based)")
    name: str = Field(description="Human-readable fan name")
    current_rpm: float = Field(ge=0, description="Current RPM")
    min_rpm: float = Field(ge=0, description="Minimum RPM")
    max_rpm: float = Field(ge=0, description="Maximum RPM")
    target_rpm: float = Field(ge=0, description="Target RPM (0 = auto)")
    mode: FanControlMode = Field(description="Current control mode")

    @property
    def percentage(self) -> float:
        """Return current speed as a percentage of the min–max range."""
        span = self.max_rpm - self.min_rpm
        if span <= 0:
            return 0.0
        return (self.current_rpm - self.min_rpm) / span * 100.0


class FanProfile(BaseModel):
    """A fan control profile configuration."""

    model_config = ConfigDict(frozen=True)

    fan_index: int = Field(ge=0, description="Fan index this profile applies to")
    mode: FanControlMode = Field(description="Control mode")
    constant_rpm: float | None = Field(
        default=None, ge=0, description="Target RPM for constant mode"
    )
    sensor_key: str | None = Field(
        default=None, description="SMC key of linked sensor for sensor-based mode"
    )
    temp_low_c: float | None = Field(
        default=None,
        description="Temperature at which fan starts ramping up",
    )
    temp_high_c: float | None = Field(
        default=None,
        description="Temperature at which fan reaches max speed",
    )

    @model_validator(mode="after")
    def _validate_mode_fields(self) -> "FanProfile":
        """Ensure mode-specific fields are present."""
        if self.mode == FanControlMode.CONSTANT and self.constant_rpm is None:
            raise ValueError("constant_rpm is required when mode is 'constant'")
        if self.mode == FanControlMode.SENSOR_BASED and self.sensor_key is None:
            raise ValueError("sensor_key is required when mode is 'sensor_based'")
        return self

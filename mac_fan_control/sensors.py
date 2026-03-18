"""Temperature sensor discovery and reading via SMC.

Provides ``SensorService`` which reads temperature values from the Apple SMC
and maps raw keys to human-readable sensor names.
"""

from mac_fan_control.exceptions import SMCKeyNotFoundError, SensorNotFoundError
from mac_fan_control.models import TemperatureSensor
from mac_fan_control.smc import SMCConnection

# ---------------------------------------------------------------------------
# Well-known SMC temperature key → human name mapping
# ---------------------------------------------------------------------------

KNOWN_SENSOR_NAMES: dict[str, str] = {
    # CPU
    "TC0P": "CPU Proximity",
    "TC0H": "CPU Heatsink",
    "TC0D": "CPU Die",
    "TC0E": "CPU VRM",
    "TC0F": "CPU VCCIO",
    "TC1C": "CPU Core 1",
    "TC2C": "CPU Core 2",
    "TC3C": "CPU Core 3",
    "TC4C": "CPU Core 4",
    "TC5C": "CPU Core 5",
    "TC6C": "CPU Core 6",
    "TC7C": "CPU Core 7",
    "TC8C": "CPU Core 8",
    "TCXC": "CPU PECI",
    "TCSA": "CPU System Agent",
    "TCGC": "CPU GPU Core",
    # GPU
    "TG0P": "GPU Proximity",
    "TG0D": "GPU Die",
    "TG0H": "GPU Heatsink",
    "TG1D": "GPU Die (dGPU)",
    # Memory
    "Tm0P": "Memory Proximity",
    "TM0S": "Memory Slot 1",
    "TM1S": "Memory Slot 2",
    # Battery
    "TB0T": "Battery TS_MAX",
    "TB1T": "Battery 1",
    "TB2T": "Battery 2",
    # Storage
    "TH0P": "HDD Proximity",
    "TH0a": "HDD Bay 1",
    "TH0b": "HDD Bay 2",
    # Mainboard / Misc
    "Ts0P": "Palm Rest",
    "Ts0S": "Palm Rest 2",
    "TA0P": "Ambient",
    "TA1P": "Ambient 2",
    "TW0P": "Airport Proximity",
    "TL0P": "LCD Proximity",
    "TI0P": "Thunderbolt Proximity",
    "TN0P": "Northbridge Proximity",
    "TN0D": "Northbridge Die",
    "Tp0P": "Power Supply Proximity",
    "TO0P": "Optical Drive",
    "TPCD": "Platform Controller Hub Die",
    # Apple Silicon (M-series) SoC sensors
    "Tp0C": "SoC CPU Efficiency Core 1",
    "Tp01": "SoC CPU Efficiency Core 2",
    "Tp05": "SoC CPU Performance Core 1",
    "Tp09": "SoC CPU Performance Core 2",
    "Tp0D": "SoC CPU Performance Core 3",
    "Tp11": "SoC CPU Performance Core 4",
    "Tp0a": "SoC GPU",
    "Tp15": "SoC GPU 2",
    "Ts1P": "SoC Proximity",
    "Ts1S": "SoC Proximity 2",
}

_TEMP_MIN_C = -40.0
_TEMP_MAX_C = 200.0


class SensorService:
    """High-level service for reading temperature sensors.

    Args:
        smc: An open ``SMCConnection`` (or compatible mock).
    """

    def __init__(self, smc: SMCConnection) -> None:
        self._smc = smc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_sensor(self, key: str) -> TemperatureSensor:
        """Read a single temperature sensor by its SMC key.

        Args:
            key: 4-character SMC key, e.g. ``"TC0P"``.

        Returns:
            A populated ``TemperatureSensor`` instance.

        Raises:
            SensorNotFoundError: If the key does not exist on this machine.
        """
        try:
            temp = self._smc.read_key_float(key)
        except (SMCKeyNotFoundError, Exception) as exc:
            raise SensorNotFoundError(
                f"Sensor not found: {key}"
            ) from exc

        name = KNOWN_SENSOR_NAMES.get(key, key)
        return TemperatureSensor(key=key, name=name, temperature_c=temp)

    def list_sensors(self) -> list[TemperatureSensor]:
        """Discover and read all known temperature sensors present on this Mac.

        Iterates over ``KNOWN_SENSOR_NAMES`` and silently skips keys that
        are not available on the current hardware.

        Returns:
            List of ``TemperatureSensor`` for every key that returned a
            plausible temperature reading.
        """
        sensors: list[TemperatureSensor] = []
        for key in KNOWN_SENSOR_NAMES:
            try:
                sensor = self.read_sensor(key)
            except SensorNotFoundError:
                continue
            if _TEMP_MIN_C <= sensor.temperature_c <= _TEMP_MAX_C:
                sensors.append(sensor)
        return sensors

    def probe_keys(self, keys: list[str]) -> list[TemperatureSensor]:
        """Probe arbitrary SMC keys and return those with valid temperature data.

        Args:
            keys: List of 4-character SMC key strings to probe.

        Returns:
            List of ``TemperatureSensor`` for keys that returned a
            temperature in the plausible range (-40 .. 200 °C).
        """
        sensors: list[TemperatureSensor] = []
        for key in keys:
            try:
                sensor = self.read_sensor(key)
            except SensorNotFoundError:
                continue
            if _TEMP_MIN_C <= sensor.temperature_c <= _TEMP_MAX_C:
                sensors.append(sensor)
        return sensors

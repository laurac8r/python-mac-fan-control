# python-mac-fan-control

Python rewrite of [Macs Fan Control](https://crystalidea.com/macs-fan-control) — monitor temperature sensors and control
fan speeds on macOS via the Apple SMC (System Management Controller).

## Requirements

- **macOS** (uses IOKit to talk to the AppleSMC driver)
- **Python 3.11+**
- Root/admin privileges for fan speed writes (Intel Macs only — see
  [Apple Silicon note](#apple-silicon-limitation) below)

## Installation

```bash
# Create a venv with uv
uv venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
uv pip install -e ".[dev]"
```

## Usage

```bash
# Show fans + sensors
mac-fan-control status

# Temperatures in Fahrenheit with decimal precision
mac-fan-control status --fahrenheit --precise

# List fans only
mac-fan-control fans

# List sensors only
mac-fan-control sensors

# Set fan 0 to 3000 RPM (requires root)
sudo mac-fan-control set 0 3000

# Reset fan 0 to automatic
sudo mac-fan-control reset 0

# Reset all fans to automatic
sudo mac-fan-control reset --all
```

## Architecture

```
mac_fan_control/
├── __init__.py       # Package version
├── exceptions.py     # Domain-specific exceptions
├── models.py         # Pydantic V2 data models (TemperatureSensor, FanStatus, FanProfile)
├── smc.py            # Low-level SMC interface (IOKit ctypes + codec functions)
├── sensors.py        # Temperature sensor discovery & reading (SensorService)
├── fans.py           # Fan discovery, status & speed control (FanService)
└── cli.py            # Click CLI entry point
```

- **`smc.py`** — ctypes bindings to IOKit's `AppleSMC` driver. Codec functions for SMC data types: `fpe2`, `sp78`,
  `flt`, `ui8`, `ui16`, `ui32`.
- **`models.py`** — Immutable Pydantic V2 models with validation. `FanProfile` supports auto, constant RPM, and
  sensor-based modes.
- **`sensors.py`** — `SensorService` discovers and reads ~50 known temperature sensor keys, with fallback for unknown
  keys.
- **`fans.py`** — `FanService` reads fan count/status, sets constant speed (clamped to min/max), and resets to auto.
- **`cli.py`** — Click group with `status`, `fans`, `sensors`, `set`, and `reset` subcommands.

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=mac_fan_control --cov-report=term-missing
```

All SMC/IOKit calls are mocked in tests — the full suite runs without hardware access.

## Apple Silicon Limitation

On Apple Silicon Macs (M1/M2/M3/M4), the AppleSMC kernel extension **silently
ignores all direct IOKit writes** from userspace — even with root privileges.
The `set` and `reset` commands will detect this and show a clear error:

```
Error: Write to F0Mn was silently ignored (wrote 5000, read back 2317).
On Apple Silicon, fan control requires a signed privileged helper.
Use Macs Fan Control.app for fan speed changes.
```

**What works on Apple Silicon:**
- `status`, `fans`, `sensors` — full temperature and fan monitoring ✅

**What doesn't work:**
- `set`, `reset` — fan speed control ❌

**Why:** The original Macs Fan Control app solves this with a code-signed
XPC privileged helper (`com.crystalidea.macsfancontrol.smcwrite`) installed
via `SMJobBless`. This helper runs as a LaunchDaemon with special entitlements
that allow SMC writes. Replicating this requires an Apple Developer certificate
and code signing, which is outside the scope of this Python rewrite.

**On Intel Macs**, direct IOKit SMC writes work with `sudo` and the `set`/`reset`
commands should function normally.

## License

MIT

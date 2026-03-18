"""Domain-specific exceptions for mac_fan_control."""


class MacFanControlError(Exception):
    """Base exception for all mac_fan_control errors."""


class SMCError(MacFanControlError):
    """Raised when an SMC operation fails."""


class SMCKeyNotFoundError(SMCError):
    """Raised when a requested SMC key does not exist."""


class SMCReadError(SMCError):
    """Raised when reading an SMC key fails."""


class SMCWriteError(SMCError):
    """Raised when writing to an SMC key fails."""


class SMCConnectionError(SMCError):
    """Raised when unable to connect to the SMC driver."""


class FanNotFoundError(MacFanControlError):
    """Raised when a requested fan index does not exist."""


class SensorNotFoundError(MacFanControlError):
    """Raised when a requested sensor key does not exist."""


class SMCWriteVerificationError(SMCWriteError):
    """Raised when an SMC write succeeds but the value does not persist.

    On Apple Silicon Macs, the SMC silently ignores direct IOKit writes.
    Fan control requires a signed privileged helper (XPC service).
    """

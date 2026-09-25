"""Stable command-line error codes and exit statuses."""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Mapping


class ExitCode(IntEnum):
    OK = 0
    INTERNAL_ERROR = 1
    USAGE_ERROR = 2
    CONFIGURATION_ERROR = 3
    CAPABILITY_DENIED = 4
    HARDWARE_ERROR = 5


class CliError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: ExitCode,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema": "rocell.error.v1",
            "error": {
                "code": self.code,
                "message": self.message,
            },
        }
        if self.details:
            value["error"]["details"] = self.details
        return value


class UsageError(CliError):
    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(code, message, exit_code=ExitCode.USAGE_ERROR, details=details)


class ConfigurationError(CliError):
    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(code, message, exit_code=ExitCode.CONFIGURATION_ERROR, details=details)


class CapabilityDeniedError(CliError):
    def __init__(
        self,
        capability: str,
        reasons: tuple[str, ...] | list[str],
    ) -> None:
        reason_list = list(dict.fromkeys(reasons))
        super().__init__(
            "CAPABILITY_DENIED",
            f"Capability {capability!r} is blocked by the current immutable build snapshot",
            exit_code=ExitCode.CAPABILITY_DENIED,
            details={"capability": capability, "reasons": reason_list},
        )


class HardwareError(CliError):
    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(code, message, exit_code=ExitCode.HARDWARE_ERROR, details=details)

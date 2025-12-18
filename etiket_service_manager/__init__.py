"""
eTiKeT Service Manager - Cross-platform service management library.

This library provides a unified interface for managing services across
Linux (systemd), macOS (launchd), and Windows (scheduled tasks).
"""
__version__ = "0.1.1"

from etiket_service_manager.manager import ServiceManager
from etiket_service_manager.config import ServiceConfig
from etiket_service_manager.status import (
    ServiceStatus,
    InstallationStatus,
    EnablementStatus,
    RunningStatus,
)
from etiket_service_manager.exceptions import (
    ServiceManagerError,
    ServiceNotInstalledError,
    ServiceAlreadyInstalledError,
    ServiceAlreadyEnabledError,
    ServiceAlreadyDisabledError,
    ServiceAlreadyRunningError,
    ServiceAlreadyStoppedError,
    ServiceOperationError,
    ServiceOperation,
)

__all__ = [
    # Main classes
    "ServiceManager",
    "ServiceConfig",
    # Status types
    "ServiceStatus",
    "InstallationStatus",
    "EnablementStatus",
    "RunningStatus",
    # Exceptions
    "ServiceManagerError",
    "ServiceNotInstalledError",
    "ServiceAlreadyInstalledError",
    "ServiceAlreadyEnabledError",
    "ServiceAlreadyDisabledError",
    "ServiceAlreadyRunningError",
    "ServiceAlreadyStoppedError",
    "ServiceOperationError",
    "ServiceOperation",
]


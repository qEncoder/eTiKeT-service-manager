"""Service manager exceptions."""

from enum import Enum


class ServiceOperation(Enum):
    """Operations that can be performed on a service."""
    INSTALL = 'install'
    UNINSTALL = 'uninstall'
    ENABLE = 'enable'
    DISABLE = 'disable'
    START = 'start'
    STOP = 'stop'
    GET_STATUS = 'getStatus'
    GET_VERSION = 'getVersion'


class ServiceManagerError(Exception):
    """Base exception for service manager errors."""
    pass


class ServiceNotInstalledError(ServiceManagerError):
    """Raised when an operation requires the service to be installed."""
    pass


class ServiceAlreadyInstalledError(ServiceManagerError):
    """Raised when trying to install a service that is already installed."""
    pass


class ServiceAlreadyEnabledError(ServiceManagerError):
    """Raised when trying to enable a service that is already enabled."""
    pass


class ServiceAlreadyDisabledError(ServiceManagerError):
    """Raised when trying to disable a service that is already disabled."""
    pass


class ServiceAlreadyRunningError(ServiceManagerError):
    """Raised when trying to start a service that is already running."""
    pass


class ServiceAlreadyStoppedError(ServiceManagerError):
    """Raised when trying to stop a service that is already stopped."""
    pass


class ServiceOperationError(ServiceManagerError):
    """Raised when a service operation fails."""
    
    def __init__(self, operation: ServiceOperation, message: str):
        super().__init__(f"Operation {operation.value} failed: {message}")
        self.operation = operation
        self.message = message


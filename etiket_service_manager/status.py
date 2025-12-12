"""Service status types and enums."""

from enum import Enum


class InstallationStatus(Enum):
    """Status indicating whether a service is installed."""
    INSTALLED = "INSTALLED"
    NOT_INSTALLED = "NOT_INSTALLED"


class EnablementStatus(Enum):
    """Status indicating whether a service is enabled to start at boot."""
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


class RunningStatus(Enum):
    """Status indicating whether a service is currently running."""
    RUNNING = "RUNNING"
    NOT_RUNNING = "NOT_RUNNING"


class ServiceStatus:
    """Combined status of a service."""
    
    def __init__(
        self,
        installation_status: InstallationStatus,
        enablement_status: EnablementStatus,
        running_status: RunningStatus
    ):
        self.installation_status = installation_status
        self.enablement_status = enablement_status
        self.running_status = running_status

    def __str__(self) -> str:
        return (
            f'ServiceStatus('
            f'installation={self.installation_status.name}, '
            f'enablement={self.enablement_status.name}, '
            f'running={self.running_status.name})'
        )

    def __repr__(self) -> str:
        return self.__str__()


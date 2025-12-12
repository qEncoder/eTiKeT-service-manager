"""Abstract base class for platform-specific service managers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List
import logging

from packaging.version import Version

from etiket_service_manager.status import ServiceStatus


class ServiceManagerBackend(ABC):
    """Abstract base class for platform-specific service manager implementations."""
    
    def __init__(self, service_name: str, app_dir: Path):
        """
        Initialize the service manager backend.
        
        Args:
            service_name: Name of the service.
            app_dir: Directory where the service application resides.
        """
        self.service_name = service_name
        self.app_dir = app_dir
        self.logger = logging.getLogger(f'{self.__class__.__name__}.{service_name}')

    @abstractmethod
    def install(
        self,
        program_arguments: List[str],
        version: Version,
        raise_if_already_installed: bool = False
    ) -> None:
        """
        Install the service.
        
        Args:
            program_arguments: List of program arguments where the first element is the executable.
            version: Version of the service being installed.
            raise_if_already_installed: If True, raise exception if already installed.
        """
        pass

    @abstractmethod
    def uninstall(self, raise_if_not_installed: bool = False) -> None:
        """
        Uninstall the service.
        
        Args:
            raise_if_not_installed: If True, raise exception if not installed.
        """
        pass

    @abstractmethod
    def enable(self, raise_if_already_enabled: bool = False) -> None:
        """
        Enable the service to start at boot.
        
        Args:
            raise_if_already_enabled: If True, raise exception if already enabled.
        """
        pass

    @abstractmethod
    def disable(self, raise_if_already_disabled: bool = False) -> None:
        """
        Disable the service from starting at boot.
        
        Args:
            raise_if_already_disabled: If True, raise exception if already disabled.
        """
        pass

    @abstractmethod
    def start(self, raise_if_already_running: bool = False) -> None:
        """
        Start the service.
        
        Args:
            raise_if_already_running: If True, raise exception if already running.
        """
        pass

    @abstractmethod
    def stop(self, raise_if_already_stopped: bool = False) -> None:
        """
        Stop the service.
        
        Args:
            raise_if_already_stopped: If True, raise exception if already stopped.
        """
        pass

    @property
    @abstractmethod
    def status(self) -> ServiceStatus:
        """Get the current status of the service."""
        pass

    @property
    @abstractmethod
    def version(self) -> Optional[Version]:
        """Get the installed version of the service, or None if not installed."""
        pass


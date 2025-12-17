"""Service manager - cross-platform service management."""

import platform
from pathlib import Path
from typing import Optional, List

from packaging.version import Version

from etiket_service_manager.config import ServiceConfig
from etiket_service_manager.status import ServiceStatus
from etiket_service_manager.backends.base import ServiceManagerBackend
from etiket_service_manager.backends.linux import LinuxServiceManager
from etiket_service_manager.backends.macos import MacOSServiceManager
from etiket_service_manager.backends.windows import WindowsServiceManager

class ServiceManager:
    """
    Cross-platform service manager.
    
    Provides a unified interface for managing services across Linux, macOS, and Windows.
    Automatically selects the appropriate backend based on the current platform.
    """
    
    def __init__(self, config: ServiceConfig):
        """
        Initialize the service manager.
        
        Args:
            config: Service configuration.
        
        Raises:
            NotImplementedError: If the current platform is not supported.
        """
        self.config = config
        self._backend: ServiceManagerBackend

        system = platform.system()
        if system == 'Windows':
            self._backend = WindowsServiceManager(config.service_name, config.app_dir)
        elif system == 'Darwin':
            self._backend = MacOSServiceManager(config.service_name, config.app_dir)
        elif system == 'Linux':
            self._backend = LinuxServiceManager(config.service_name, config.app_dir)
        else:
            raise NotImplementedError(f'Unsupported platform: {system}')

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
        
        Raises:
            FileNotFoundError: If the executable (first argument) doesn't exist.
            ServiceAlreadyInstalledError: If service is already installed and raise_if_already_installed is True.
            ServiceOperationError: If installation fails.
        """
        # Validate that first argument (executable) exists if it's an absolute path
        executable_path = Path(program_arguments[0])
        if executable_path.is_absolute() and not executable_path.exists():
            raise FileNotFoundError(f'Executable does not exist: {executable_path}')
        
        self._backend.install(program_arguments, version, raise_if_already_installed)

    def uninstall(self, raise_if_not_installed: bool = False) -> None:
        """
        Uninstall the service.
        
        Args:
            raise_if_not_installed: If True, raise exception if not installed.
        
        Raises:
            ServiceNotInstalledError: If service is not installed and raise_if_not_installed is True.
            ServiceOperationError: If uninstallation fails.
        """
        self._backend.uninstall(raise_if_not_installed)

    def enable(self, raise_if_already_enabled: bool = False) -> None:
        """
        Enable the service to start at boot.
        
        Args:
            raise_if_already_enabled: If True, raise exception if already enabled.
        
        Raises:
            ServiceNotInstalledError: If service is not installed.
            ServiceAlreadyEnabledError: If service is already enabled and raise_if_already_enabled is True.
            ServiceOperationError: If enabling fails.
        """
        self._backend.enable(raise_if_already_enabled)

    def disable(self, raise_if_already_disabled: bool = False) -> None:
        """
        Disable the service from starting at boot.
        
        Args:
            raise_if_already_disabled: If True, raise exception if already disabled.
        
        Raises:
            ServiceNotInstalledError: If service is not installed.
            ServiceAlreadyDisabledError: If service is already disabled and raise_if_already_disabled is True.
            ServiceOperationError: If disabling fails.
        """
        self._backend.disable(raise_if_already_disabled)

    def start(self, raise_if_already_running: bool = False) -> None:
        """
        Start the service.
        
        Args:
            raise_if_already_running: If True, raise exception if already running.
        
        Raises:
            ServiceNotInstalledError: If service is not installed.
            ServiceAlreadyRunningError: If service is already running and raise_if_already_running is True.
            ServiceOperationError: If starting fails.
        """
        self._backend.start(raise_if_already_running)

    def stop(self, raise_if_already_stopped: bool = False) -> None:
        """
        Stop the service.
        
        Args:
            raise_if_already_stopped: If True, raise exception if already stopped.
        
        Raises:
            ServiceNotInstalledError: If service is not installed.
            ServiceAlreadyStoppedError: If service is already stopped and raise_if_already_stopped is True.
            ServiceOperationError: If stopping fails.
        """
        self._backend.stop(raise_if_already_stopped)

    @property
    def name(self) -> str:
        """Get the service name."""
        return self._backend.service_name

    @property
    def status(self) -> ServiceStatus:
        """Get the current status of the service."""
        return self._backend.status

    @property
    def version(self) -> Optional[Version]:
        """Get the installed version of the service, or None if not installed."""
        return self._backend.version

"""Linux systemd service manager backend."""

import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Callable, List

from packaging.version import Version

from etiket_service_manager.backends.base import (
    ServiceManagerBackend,
    DEFAULT_STATUS_WAIT_TIMEOUT_SECONDS,
    DEFAULT_POLL_INTERVAL_MS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from etiket_service_manager.backends.linux_templates import SYSTEMD_SERVICE_TEMPLATE
from etiket_service_manager.status import (
    ServiceStatus, InstallationStatus, EnablementStatus, RunningStatus
)
from etiket_service_manager.exceptions import (
    ServiceOperation, ServiceOperationError, ServiceNotInstalledError,
    ServiceAlreadyInstalledError, ServiceAlreadyEnabledError,
    ServiceAlreadyDisabledError, ServiceAlreadyRunningError,
    ServiceAlreadyStoppedError
)


class LinuxServiceManager(ServiceManagerBackend):
    """Linux systemd user service manager."""
    
    def __init__(self, service_name: str, app_dir: Path):
        super().__init__(service_name, app_dir)
        home = Path.home()
        self.systemd_user_dir = home / '.config' / 'systemd' / 'user'
        self.service_file_path = self.systemd_user_dir / f'{service_name}.service'
        
        self.logger.info('LinuxServiceManager initialized for service: %s', service_name)
        self.logger.debug('service_file_path: %s, app_dir: %s', self.service_file_path, self.app_dir)

    def install(
        self,
        program_arguments: List[str],
        version: Version,
        raise_if_already_installed: bool = False
    ) -> None:
        self.logger.info('Installing service: %s, version: %s with args: %s', self.service_name, version, program_arguments)
        current_status = self.status
        
        if current_status.installation_status == InstallationStatus.INSTALLED:
            if raise_if_already_installed:
                raise ServiceAlreadyInstalledError()
            self.logger.debug('Service is already installed, skipping')
            return

        try:
            self.logger.info('Creating directories: %s', self.app_dir)
            os.makedirs(self.app_dir, exist_ok=True)
            os.makedirs(self.systemd_user_dir, exist_ok=True)

            exec_start = ' '.join(shlex.quote(arg) for arg in program_arguments)

            self.logger.info('Creating systemd service file at %s', self.service_file_path)
            service_file_content = SYSTEMD_SERVICE_TEMPLATE.format(
                service_name=self.service_name,
                exec_start=exec_start,
                working_directory=self.app_dir,
                version=str(version)
            )
            self.service_file_path.write_text(service_file_content)

            reload_result = subprocess.run(
                ['systemctl', '--user', 'daemon-reload'],
                capture_output=True, text=True, check=False, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
            )
            if reload_result.returncode != 0:
                self.logger.error('Failed to reload systemd: %s', reload_result.stderr)
                raise ServiceOperationError(ServiceOperation.INSTALL, f'Failed to reload systemd: {reload_result.stderr}')

            self.enable()
            self.start()

            self.logger.info('Successfully installed and started service: %s', self.service_name)

        except Exception as e:
            self.logger.error('Installation failed, attempting cleanup: %s', e)
            try:
                self.uninstall()
            except Exception:
                pass
            
            if isinstance(e, ServiceOperationError):
                raise
            raise ServiceOperationError(ServiceOperation.INSTALL, f'Installation failed: {e}') from e

    def uninstall(self, raise_if_not_installed: bool = False) -> None:
        self.logger.info('Uninstalling service: %s', self.service_name)
        
        current_status = self.status
        if current_status.installation_status == InstallationStatus.NOT_INSTALLED:
            self.logger.info('Service %s is not installed', self.service_name)
            if raise_if_not_installed:
                raise ServiceNotInstalledError()
            self.logger.debug('Service is not installed, skipping')
            return

        if current_status.running_status == RunningStatus.RUNNING:
            self.logger.info('Service is running, stopping first')
            self.stop()

        if current_status.enablement_status == EnablementStatus.ENABLED:
            self.logger.info('Service is enabled, disabling first')
            self.disable()

        if self.service_file_path.exists():
            self.logger.info('Removing service file: %s', self.service_file_path)
            self.service_file_path.unlink()

        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=False, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)

        if self.app_dir.exists():
            self.logger.info('Removing service directory: %s', self.app_dir)
            shutil.rmtree(self.app_dir)

        self.logger.info('Service %s successfully uninstalled', self.service_name)

    def enable(self, raise_if_already_enabled: bool = False) -> None:
        self.logger.info('Enabling service: %s', self.service_name)
        
        current_status = self.status
        if current_status.installation_status == InstallationStatus.NOT_INSTALLED:
            self.logger.warning('Service is not installed')
            raise ServiceNotInstalledError()
        
        if current_status.enablement_status == EnablementStatus.ENABLED:
            if raise_if_already_enabled:
                self.logger.warning('Service is already enabled')
                raise ServiceAlreadyEnabledError()
            self.logger.debug('Service is already enabled, skipping')
            return

        result = subprocess.run(
            ['systemctl', '--user', 'enable', f'{self.service_name}.service'],
            capture_output=True, text=True, check=False, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
        )
        if result.returncode != 0:
            self.logger.error('Failed to enable service: %s', result.stderr)
            raise ServiceOperationError(ServiceOperation.ENABLE, f'Failed to enable service: {result.stderr}')
        
        self.logger.info('Service %s successfully enabled', self.service_name)

    def disable(self, raise_if_already_disabled: bool = False) -> None:
        self.logger.info('Disabling service: %s', self.service_name)
        
        current_status = self.status
        if current_status.installation_status == InstallationStatus.NOT_INSTALLED:
            self.logger.warning('Service is not installed')
            raise ServiceNotInstalledError()
        
        if current_status.enablement_status == EnablementStatus.DISABLED:
            if raise_if_already_disabled:
                self.logger.warning('Service is already disabled')
                raise ServiceAlreadyDisabledError()
            self.logger.debug('Service is already disabled, skipping')
            return

        if current_status.running_status == RunningStatus.RUNNING:
            self.logger.info('Service is running, stopping first')
            self.stop()

        result = subprocess.run(
            ['systemctl', '--user', 'disable', f'{self.service_name}.service'],
            capture_output=True, text=True, check=False, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
        )
        if result.returncode != 0:
            self.logger.error('Failed to disable service: %s', result.stderr)
            raise ServiceOperationError(ServiceOperation.DISABLE, f'Failed to disable service: {result.stderr}')
        
        self.logger.info('Service %s successfully disabled', self.service_name)

    def start(self, raise_if_already_running: bool = False) -> None:
        self.logger.info('Starting service: %s', self.service_name)
        
        current_status = self.status
        if current_status.installation_status == InstallationStatus.NOT_INSTALLED:
            self.logger.warning('Service is not installed')
            raise ServiceNotInstalledError()

        if current_status.enablement_status == EnablementStatus.DISABLED:
            self.logger.info('Service is disabled, enabling first')
            self.enable()

        if current_status.running_status == RunningStatus.RUNNING:
            if raise_if_already_running:
                self.logger.warning('Service is already running')
                raise ServiceAlreadyRunningError()
            self.logger.debug('Service is already running, skipping')
            return

        result = subprocess.run(
            ['systemctl', '--user', 'start', f'{self.service_name}.service'],
            capture_output=True, text=True, check=False, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
        )
        if result.returncode != 0:
            self.logger.error('Failed to start service: %s', result.stderr)
            raise ServiceOperationError(ServiceOperation.START, f'Failed to start service: {result.stderr}')

        if not self._wait_for_service_status(lambda s: s.running_status == RunningStatus.RUNNING):
            raise ServiceOperationError(ServiceOperation.START, 'Service did not start within timeout')
        self.logger.info('Service %s successfully started', self.service_name)

    def stop(self, raise_if_already_stopped: bool = False) -> None:
        self.logger.info('Stopping service: %s', self.service_name)
        
        current_status = self.status
        if current_status.installation_status == InstallationStatus.NOT_INSTALLED:
            self.logger.warning('Service is not installed')
            raise ServiceNotInstalledError()

        if current_status.running_status == RunningStatus.NOT_RUNNING:
            if raise_if_already_stopped:
                self.logger.warning('Service is not running')
                raise ServiceAlreadyStoppedError()
            self.logger.debug('Service is not running, skipping')
            return

        result = subprocess.run(
            ['systemctl', '--user', 'stop', f'{self.service_name}.service'],
            capture_output=True, text=True, check=False, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
        )
        if result.returncode != 0:
            self.logger.error('Failed to stop service: %s', result.stderr)
            raise ServiceOperationError(ServiceOperation.STOP, f'Failed to stop service: {result.stderr}')

        if not self._wait_for_service_status(lambda s: s.running_status == RunningStatus.NOT_RUNNING):
            raise ServiceOperationError(ServiceOperation.STOP, 'Service did not stop within timeout')
        self.logger.info('Service %s successfully stopped', self.service_name)

    @property
    def status(self) -> ServiceStatus:
        self.logger.debug('Checking status of service: %s', self.service_name)
        
        service_status = ServiceStatus(
            InstallationStatus.NOT_INSTALLED,
            EnablementStatus.DISABLED,
            RunningStatus.NOT_RUNNING
        )

        if self.service_file_path.exists():
            service_status.installation_status = InstallationStatus.INSTALLED
        else:
            return service_status

        # Check enabled
        result_enabled = subprocess.run(
            ['systemctl', '--user', 'is-enabled', f'{self.service_name}.service'],
            capture_output=True, text=True, check=False, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
        )
        if result_enabled.returncode == 0:
            service_status.enablement_status = EnablementStatus.ENABLED
        
        # Check active (running)
        result_active = subprocess.run(
            ['systemctl', '--user', 'is-active', f'{self.service_name}.service'],
            capture_output=True, text=True, check=False, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
        )
        if result_active.returncode == 0:
            service_status.running_status = RunningStatus.RUNNING

        self.logger.info('Service %s status: %s', self.service_name, service_status)
        return service_status

    @property
    def version(self) -> Optional[Version]:
        self.logger.debug('Getting version for service: %s', self.service_name)
        
        try:
            if not self.service_file_path.exists():
                self.logger.warning('Service file not found, service may not be installed')
                return None
            
            content = self.service_file_path.read_text()
            match = re.search(r'Environment="VERSION=([^"]+)"', content)
            if match:
                version_str = match.group(1)
                self.logger.debug('Found version: %s', version_str)
                return Version(version_str)
            
            self.logger.warning('Version information not found in service file')
            return None

        except Exception as e:
            self.logger.error('Error getting service version: %s', e)
            return None

    def _wait_for_service_status(
        self,
        predicate: Callable[[ServiceStatus], bool],
        timeout_seconds: int = DEFAULT_STATUS_WAIT_TIMEOUT_SECONDS,
        poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS
    ) -> bool:
        self.logger.info('Waiting for service %s status to change (timeout: %ss)', self.service_name, timeout_seconds)
        start_time = time.time()
        
        while (time.time() - start_time) < timeout_seconds:
            current_status = self.status
            if predicate(current_status):
                elapsed = (time.time() - start_time) * 1000
                self.logger.info('Service %s reached desired status after %.0fms', self.service_name, elapsed)
                return True
            
            time.sleep(poll_interval_ms / 1000.0)
            
        self.logger.warning('Timeout reached while waiting for %s status change', self.service_name)
        return False


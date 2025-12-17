"""macOS launchd service manager backend."""

import os, plistlib, re, shutil, subprocess, time

from pathlib import Path
from typing import Optional, Callable, List

from packaging.version import Version

from etiket_service_manager.backends.base import ServiceManagerBackend
from etiket_service_manager.status import (
    ServiceStatus, InstallationStatus, EnablementStatus, RunningStatus
)
from etiket_service_manager.exceptions import (
    ServiceOperation, ServiceOperationError, ServiceNotInstalledError,
    ServiceAlreadyInstalledError, ServiceAlreadyEnabledError,
    ServiceAlreadyDisabledError, ServiceAlreadyRunningError,
    ServiceAlreadyStoppedError
)


class MacOSServiceManager(ServiceManagerBackend):
    """macOS launchd service manager."""
    
    def __init__(self, service_name: str, app_dir: Path):
        super().__init__(service_name, app_dir)
        self.user_id = str(os.getuid())
        self.bundle_identifier = f'com.qharbor.{service_name}'
        home = Path.home()
        self.plist_path = home / 'Library' / 'LaunchAgents' / f'{self.bundle_identifier}.plist'
        
        self.logger.info('MacOSServiceManager initialized for service: %s', service_name)
        self.logger.debug('plist_path: %s, app_dir: %s', self.plist_path, self.app_dir)

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
            log_dir = self.app_dir / f'{self.service_name}_logs'

            self.logger.info('Creating directories: %s and %s', self.app_dir, log_dir)
            os.makedirs(log_dir, exist_ok=True)

            # Create plist content
            plist_content = {
                'KeepAlive': True,
                'Label': self.bundle_identifier,
                'WorkingDirectory': str(self.app_dir),
                'ProgramArguments': program_arguments,
                'RunAtLoad': True,
                'StandardErrorPath': str(log_dir / "err.log"),
                'StandardOutPath': str(log_dir / "out.log"),
                'ThrottleInterval': 60,
                'Version': str(version)
            }

            # Create plist file
            self.logger.info('Creating plist file at %s', self.plist_path)
            with open(self.plist_path, 'wb') as f:
                plistlib.dump(plist_content, f)

            try:
                os.chmod(self.plist_path, 0o644)
            except OSError as e:
                self.logger.warning('Failed to set plist permissions: %s', e)

            self.enable()
            self.start()

            self.logger.info('Successfully installed and started service: %s', self.service_name)

        except Exception as e:
            self.logger.error('Installation failed, attempting cleanup: %s', e)
            self.uninstall()
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

        if self.plist_path.exists():
            try:
                self.logger.info('Deleting plist file: %s', self.plist_path)
                self.plist_path.unlink()
            except Exception as e:
                self.logger.error('Failed to delete plist file: %s', e)
                raise ServiceOperationError(ServiceOperation.UNINSTALL, f'Failed to delete the plist file: {e}') from e
        else:
            self.logger.info('Plist file not found. Service is not installed.')

        self.logger.info('Removing service directory: %s', self.app_dir)
        if not self.app_dir.exists():
            self.logger.warning('App directory does not exist, skipping removal')
        else:
            shutil.rmtree(self.app_dir)

        self.logger.info('Service %s successfully uninstalled', self.service_name)

    def enable(self, raise_if_already_enabled: bool = False) -> None:
        self.logger.info('Enabling service: %s', self.service_name)
        
        current_status = self.status
        if current_status.enablement_status == EnablementStatus.ENABLED:
            if raise_if_already_enabled:
                self.logger.warning('Service is already enabled')
                raise ServiceAlreadyEnabledError()
            self.logger.debug('Service is already enabled, skipping')
            return

        self.logger.info('Enabling service with launchctl')
        result = subprocess.run(
            ['launchctl', 'enable', f'gui/{self.user_id}/{self.bundle_identifier}'],
            capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            self.logger.error('Failed to enable the service: %s', result.stderr)
            raise ServiceOperationError(ServiceOperation.ENABLE, f'Failed to enable the service: {result.stderr}')
        
        self.logger.info('Service %s successfully enabled', self.service_name)

    def disable(self, raise_if_already_disabled: bool = False) -> None:
        self.logger.info('Disabling service: %s', self.service_name)
        
        self.stop()
        
        current_status = self.status
        if current_status.enablement_status == EnablementStatus.DISABLED:
            if raise_if_already_disabled:
                self.logger.warning('Service is already disabled')
                raise ServiceAlreadyDisabledError()
            self.logger.debug('Service is already disabled, skipping')
            return

        self.logger.info('Disabling service with launchctl')
        result = subprocess.run(
            ['launchctl', 'disable', f'gui/{self.user_id}/{self.bundle_identifier}'],
            capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            self.logger.error('Failed to disable the service: %s', result.stderr)
            raise ServiceOperationError(ServiceOperation.DISABLE, f'Failed to disable the service: {result.stderr}')
        
        self.logger.info('Service %s successfully disabled', self.service_name)

    def start(self, raise_if_already_running: bool = False) -> None:
        self.logger.info('Starting service: %s', self.service_name)
        
        current_status = self.status
        
        if current_status.enablement_status == EnablementStatus.DISABLED:
            self.logger.info('Service is disabled, enabling first')
            self.enable(raise_if_already_enabled=False)

        if current_status.running_status == RunningStatus.RUNNING:
            if raise_if_already_running:
                self.logger.warning('Service is already running')
                raise ServiceAlreadyRunningError()
            self.logger.debug('Service is already running, skipping')
            return

        self.logger.info('Kickstarting service with launchctl')
        
        # Try to start, retry once if it fails (e.g. if port is not released yet)
        for i in range(2):
            result = subprocess.run(
                ['launchctl', 'bootstrap', f'gui/{self.user_id}', str(self.plist_path)],
                capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                break
                
            if i == 0:
                self.logger.warning('Failed to start service, retrying in 1s: %s', result.stderr)
                time.sleep(1)
            else:
                self.logger.error('Failed to start the service: %s', result.stderr)
                raise ServiceOperationError(ServiceOperation.START, f'Failed to start the service: {result.stderr}')

        self._wait_for_service_status(lambda s: s.running_status == RunningStatus.RUNNING)
        self.logger.info('Service %s successfully started', self.service_name)

    def stop(self, raise_if_already_stopped: bool = False) -> None:
        self.logger.info('Stopping service: %s', self.service_name)
        
        current_status = self.status
        if current_status.running_status == RunningStatus.NOT_RUNNING:
            if raise_if_already_stopped:
                self.logger.warning('Service is not running')
                raise ServiceAlreadyStoppedError()
            self.logger.debug('Service is not running, skipping')
            return

        result = subprocess.run(
            ['launchctl', 'bootout', f'gui/{self.user_id}/{self.bundle_identifier}'],
            capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            self.logger.error('Failed to bootout the service: %s', result.stderr)
            raise ServiceOperationError(ServiceOperation.STOP, f'Failed to bootout the service: {result.stderr}')

        self._wait_for_service_status(lambda s: s.running_status == RunningStatus.NOT_RUNNING)
        self.logger.info('Service %s successfully stopped', self.service_name)

    @property
    def status(self) -> ServiceStatus:
        self.logger.debug('Checking status of service: %s', self.service_name)
        
        service_status = ServiceStatus(
            InstallationStatus.NOT_INSTALLED,
            EnablementStatus.DISABLED,
            RunningStatus.NOT_RUNNING
        )

        if self.plist_path.exists():
            self.logger.debug('Plist file exists, service is installed')
            service_status.installation_status = InstallationStatus.INSTALLED
        else:
            return service_status

        # Check enabled
        result_disabled = subprocess.run(
            ['launchctl', 'print-disabled', f'gui/{self.user_id}'],
            capture_output=True, text=True, check=False
        )
        if result_disabled.returncode == 0:
            output = result_disabled.stdout
            match = re.search(r'"' + re.escape(self.bundle_identifier) + r'" => (\w+)', output)
            
            if match:
                state = match.group(1)
                self.logger.debug('Service enablement state from launchctl: %s', state)
                if state == 'disabled':
                    service_status.enablement_status = EnablementStatus.DISABLED
                elif state == 'enabled':
                    service_status.enablement_status = EnablementStatus.ENABLED
                else:
                    self.logger.error('Unknown service enablement state: %s', state)
                    raise ServiceOperationError(ServiceOperation.GET_STATUS, f'Unknown service enablement state: {state}')
            else:
                self.logger.debug('Service not found in disabled list, assuming enabled')
                service_status.enablement_status = EnablementStatus.ENABLED
        else:
            self.logger.warning('Failed to check service enablement status')

        # Check running
        result_active = subprocess.run(
            ['launchctl', 'print', f'gui/{self.user_id}/{self.bundle_identifier}'],
            capture_output=True, text=True, check=False
        )
        if result_active.returncode == 0:
            output = result_active.stdout
            match = re.search(r'state\s*=\s*(\w+)', output)
            if match and match.group(1) == 'running':
                self.logger.debug('Service is running')
                service_status.running_status = RunningStatus.RUNNING
            else:
                self.logger.debug('Service is not running, state: %s', match.group(1) if match else "unknown")
        else:
            self.logger.debug('Service is not found in launchctl')

        self.logger.info('Service %s status: %s', self.service_name, service_status)
        return service_status

    @property
    def version(self) -> Optional[Version]:
        try:
            self.logger.debug('Reading version from plist file: %s', self.plist_path)
            if not self.plist_path.exists():
                self.logger.warning('Plist file not found, service may not be installed')
                return None

            with open(self.plist_path, 'rb') as f:
                plist_content = plistlib.load(f)
            
            version_str = plist_content.get('Version')
            if version_str:
                self.logger.debug('Version found in plist file: %s', version_str)
                return Version(version_str)
            else:
                self.logger.error('Failed to read version from plist file: Version key missing')
                raise ServiceOperationError(ServiceOperation.GET_VERSION, 'Failed to read version from plist file: Version key missing')

        except Exception as e:
            if isinstance(e, FileNotFoundError):
                self.logger.warning('Plist file not found, service may not be installed')
                return None
            self.logger.error('Failed to read version from plist file: %s', e)
            raise ServiceOperationError(ServiceOperation.GET_VERSION, f'Failed to read version from plist file: {e}') from e

    def _wait_for_service_status(
        self,
        predicate: Callable[[ServiceStatus], bool],
        timeout_seconds: int = 5,
        poll_interval_ms: int = 300
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


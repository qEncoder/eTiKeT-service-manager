"""Windows scheduled task service manager backend."""

import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Callable, List

from packaging.version import Version
import psutil

from etiket_service_manager.backends.base import ServiceManagerBackend
from etiket_service_manager.backends.windows_templates import (
    VBS_PROC_LAUNCHER_TEMPLATE,
    create_scheduled_task_xml
)
from etiket_service_manager.status import (
    ServiceStatus, InstallationStatus, EnablementStatus, RunningStatus
)
from etiket_service_manager.exceptions import (
    ServiceOperation, ServiceOperationError, ServiceNotInstalledError,
    ServiceAlreadyInstalledError, ServiceAlreadyEnabledError,
    ServiceAlreadyDisabledError, ServiceAlreadyRunningError,
    ServiceAlreadyStoppedError
)


class WindowsServiceManager(ServiceManagerBackend):
    """Windows scheduled task service manager."""
    
    def __init__(self, service_name: str, app_dir: Path):
        super().__init__(service_name, app_dir)
        
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

        os.makedirs(self.app_dir, exist_ok=True)

        self.logger.info('Creating VBS script to run the command in a hidden window')
        vbs_path = self.app_dir / 'run.vbs'
        
        # Build command line from program_arguments
        escaped_args = [arg.replace('"', '""') for arg in program_arguments]
        command_line = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in escaped_args)

        # PID file path (escape backslashes for VBS)
        pid_file_path = str(self.app_dir / 'service.pid').replace('\\', '\\\\')
        working_dir_path = str(self.app_dir).replace('\\', '\\\\')
        
        # Use VBS template
        vbs_content = VBS_PROC_LAUNCHER_TEMPLATE.format(
            executable=command_line,
            pid_file=pid_file_path,
            working_dir=working_dir_path
        )
        vbs_path.write_text(vbs_content)

        self.logger.info('Creating scheduled task XML for %s', self.service_name)
        xml_file_path = self._create_scheduled_task_xml(self.service_name, str(version), str(self.app_dir))

        self.logger.info('Registering scheduled task for %s', self.service_name)
        create_task_result = subprocess.run(
            ['cmd', '/c', 'schtasks', '/Create', '/TN', self.service_name, '/XML', str(xml_file_path), '/F'],
            capture_output=True, text=True, check=False
        )

        if create_task_result.returncode != 0:
            raise ServiceOperationError(ServiceOperation.INSTALL, f'Failed to create scheduled task: {create_task_result.stderr}')
        
        os.remove(xml_file_path)

        self.start()
        self.logger.info('Service %s has been installed successfully', self.service_name)

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

        self.logger.info('Removing scheduled task for %s', self.service_name)
        remove_task_result = subprocess.run(
            ['cmd', '/c', 'schtasks', '/Delete', '/TN', self.service_name, '/F'],
            capture_output=True, text=True, check=False
        )

        if remove_task_result.returncode != 0:
            raise ServiceOperationError(ServiceOperation.UNINSTALL, f'Failed to remove scheduled task: {remove_task_result.stderr}')

        self.logger.info('Removing service directory: %s', self.app_dir)
        if self.app_dir.exists():
            try:
                shutil.rmtree(self.app_dir)
            except Exception as e:
                raise ServiceOperationError(ServiceOperation.UNINSTALL, f'Failed to remove service directory: {e}') from e

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

        enable_result = subprocess.run(
            ['cmd', '/c', 'schtasks', '/Change', '/TN', self.service_name, '/ENABLE'],
            capture_output=True, text=True, check=False
        )

        if enable_result.returncode != 0:
            raise ServiceOperationError(ServiceOperation.ENABLE, f'Failed to enable scheduled task: {enable_result.stderr}')
        
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

        disable_result = subprocess.run(
            ['cmd', '/c', 'schtasks', '/Change', '/TN', self.service_name, '/DISABLE'],
            capture_output=True, text=True, check=False
        )
        
        if disable_result.returncode != 0:
            raise ServiceOperationError(ServiceOperation.DISABLE, f'Failed to disable scheduled task: {disable_result.stderr}')
        
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

        start_result = subprocess.run(
            ['cmd', '/c', 'schtasks', '/Run', '/TN', self.service_name],
            capture_output=True, text=True, check=False
        )
        
        if start_result.returncode != 0:
            raise ServiceOperationError(ServiceOperation.START, f'Failed to start scheduled task: {start_result.stderr}')

        self._wait_for_service_status(lambda s: s.running_status == RunningStatus.RUNNING)
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

        # 1. First, stop the scheduled task (kills wscript.exe - stops restart loop)
        self.logger.info('Stopping scheduled task (wscript wrapper)')
        stop_result = subprocess.run(
            ['cmd', '/c', 'schtasks', '/End', '/TN', self.service_name],
            capture_output=True, text=True, check=False
        )
        
        if stop_result.returncode != 0:
            if 'is not currently running' not in stop_result.stderr:
                self.logger.debug('schtasks /End result: %s', stop_result.stderr)

        # 2. Then kill the child process by PID from the .pid file
        pid_file = self.app_dir / 'service.pid'
        if pid_file.exists():
            try:
                data = pid_file.read_text().strip().split(',')
                pid = int(data[0])
                timestamp = data[1] if len(data) > 1 else None
                
                self.logger.info('Killing child process PID %d (created: %s)', pid, timestamp or 'unknown')
                
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    
                    # Kill the entire process tree (children first)
                    for child in proc.children(recursive=True):
                        try:
                            child.kill()
                        except psutil.NoSuchProcess:
                            pass
                    
                    try:
                        proc.kill()
                    except psutil.NoSuchProcess:
                        pass
                    
                    self.logger.info('Killed process PID %d and its children', pid)
                else:
                    self.logger.debug('Process PID %d no longer exists', pid)
                
            except (ValueError, IOError) as e:
                self.logger.warning('Failed to read PID file: %s', e)
        
        # 3. Cleanup PID file
        time.sleep(0.3)
        if pid_file.exists():
            try:
                pid_file.unlink()
            except Exception:
                pass
        
        # Final status check
        if self._wait_for_service_status(lambda s: s.running_status == RunningStatus.NOT_RUNNING, timeout_seconds=2):
            self.logger.info('Service %s successfully stopped', self.service_name)
            return
        
        self.logger.warning('Service did not stop gracefully.')
        raise ServiceOperationError(ServiceOperation.STOP, 'Service could not be stopped. Manual intervention required.')

    @property
    def status(self) -> ServiceStatus:
        self.logger.debug('Checking status of service: %s', self.service_name)
        
        service_status = ServiceStatus(
            InstallationStatus.NOT_INSTALLED,
            EnablementStatus.DISABLED,
            RunningStatus.NOT_RUNNING
        )

        try:
            # 1. Check if installed and get config via XML
            xml_result = subprocess.run(
                ['cmd', '/c', 'schtasks', '/Query', '/TN', self.service_name, '/XML'],
                capture_output=True, text=True, check=False
            )
            
            if (xml_result.returncode != 0 or 
                'ERROR: The system cannot find the file specified.' in xml_result.stderr):
                self.logger.debug('Service %s is not installed', self.service_name)
                return service_status

            service_status.installation_status = InstallationStatus.INSTALLED

            root = ET.fromstring(xml_result.stdout)
            ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
            
            settings_enabled = root.find('.//t:Settings/t:Enabled', ns)
            # Windows only includes <Enabled>false</Enabled> when disabled; missing = enabled
            if settings_enabled is None or settings_enabled.text != 'false':
                service_status.enablement_status = EnablementStatus.ENABLED
            
            # 2. Check Running State via PID file
            pid_file = self.app_dir / 'service.pid'
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip().split(',')[0])
                    if psutil.pid_exists(pid):
                        service_status.running_status = RunningStatus.RUNNING
                        self.logger.debug('Service is running (PID %d)', pid)
                    else:
                        # Stale PID file - process died but VBS didn't clean up
                        self.logger.debug('Stale PID file found (PID %d no longer exists)', pid)
                except (ValueError, IOError):
                    pass
        
        except Exception as e:
            self.logger.warning('Error getting service status: %s', e)

        self.logger.info('Service %s status: %s', self.service_name, service_status)
        return service_status

    @property
    def version(self) -> Optional[Version]:
        self.logger.debug('Getting version for service: %s', self.service_name)
        
        try:
            # Use /XML to avoid locale issues with parsing "Comment:" or "Description:" label
            result = subprocess.run(
                ['cmd', '/c', 'schtasks', '/Query', '/TN', self.service_name, '/XML'],
                capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                self.logger.warning('Failed to get service details: %s', result.stderr)
                return None
            
            # Parse XML
            try:
                root = ET.fromstring(result.stdout)
                ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
                
                desc_node = root.find('.//t:RegistrationInfo/t:Description', ns)
                if desc_node is None or not desc_node.text:
                    self.logger.warning('Description not found in task XML')
                    return None
                
                full_comment = desc_node.text.strip()
            except ET.ParseError as pe:
                self.logger.warning('Failed to parse task XML: %s', pe)
                return None
            
            self.logger.debug('Full service description: %s', full_comment)
            
            version_match = re.search(r'version=([\d]+(?:\.[\d]+)*(?:[a-zA-Z0-9._-]*)?)', full_comment)
            if not version_match:
                self.logger.warning('Version not found in description')
                return None
            
            return Version(version_match.group(1))

        except Exception as e:
            self.logger.warning('Error getting service version: %s', e)
            return None

    def _wait_for_service_status(
        self,
        predicate: Callable[[ServiceStatus], bool],
        timeout_seconds: int = 10,
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

    def _create_scheduled_task_xml(self, service_name: str, version: str, extract_dir: str) -> Path:
        sid_result = subprocess.run(
            ['cmd', '/c', 'whoami', '/user', '/fo', 'csv', '/nh'],
            capture_output=True, text=True, check=False
        )
        
        userid = ''
        user_sid = ''
        
        if sid_result.returncode == 0:
            parts = sid_result.stdout.strip().split(',')
            if len(parts) >= 2:
                userid = parts[0].replace('"', '').strip()
                user_sid = parts[1].replace('"', '').strip()
        else:
            raise ServiceOperationError(ServiceOperation.INSTALL, f'Failed to get user SID: {sid_result.stderr}')

        if not user_sid or not userid:
            raise ServiceOperationError(ServiceOperation.INSTALL, f'Failed to get user SID: {sid_result.stderr}')

        vbs_path = Path(extract_dir) / 'run.vbs'
        
        # Use template function to generate XML
        final_xml = create_scheduled_task_xml(
            service_name=service_name,
            version=version,
            vbs_path=vbs_path,
            userid=userid,
            user_sid=user_sid
        )
        
        file_path = Path(extract_dir) / 'task.xml'
        file_path.write_text(final_xml, encoding='utf-16')
        
        return file_path


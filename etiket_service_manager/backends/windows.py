"""Windows scheduled task service manager backend."""

import os
import re
import shutil
import subprocess
import time
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

        vbs_content = (
            'Dim objShell\n'
            'Set objShell=CreateObject("WScript.Shell")\n'
            f'objShell.Run "{command_line.replace(os.sep, os.sep*2)}",0,true'
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

        # Kill all procs with the name service_name
        kill_result = subprocess.run(
            ['cmd', '/c', 'taskkill', '/IM', f'{self.service_name}.exe', '/F'],
            capture_output=True, text=True, check=False
        )
        if kill_result.returncode != 0:
            raise ServiceOperationError(ServiceOperation.STOP, f'Failed to kill processes: {kill_result.stderr}')

        stop_result = subprocess.run(
            ['cmd', '/c', 'schtasks', '/End', '/TN', self.service_name],
            capture_output=True, text=True, check=False
        )
        if stop_result.returncode != 0:
            raise ServiceOperationError(ServiceOperation.STOP, f'Failed to stop scheduled task: {stop_result.stderr}')

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

        try:
            result = subprocess.run(
                ['cmd', '/c', 'schtasks', '/Query', '/TN', self.service_name, '/FO', 'LIST', '/V'],
                capture_output=True, text=True, check=False
            )
            
            stdout = result.stdout
            if (result.returncode != 0 or 
                'ERROR: The system cannot find the file specified.' in stdout or
                'TaskName:' not in stdout):
                self.logger.debug('Service %s is not installed', self.service_name)
                return service_status

            service_status.installation_status = InstallationStatus.INSTALLED

            status_match = re.search(r'Status:\s*(.*)', stdout)
            scheduled_state_match = re.search(r'Scheduled Task State:\s*(.*)', stdout)

            if status_match:
                status = status_match.group(1).strip()
                self.logger.debug('Service status: %s', status)
                if 'Running' in status:
                    service_status.running_status = RunningStatus.RUNNING
            
            if scheduled_state_match:
                state = scheduled_state_match.group(1).strip()
                self.logger.debug('Scheduled task state: %s', state)
                if state == 'Enabled':
                    service_status.enablement_status = EnablementStatus.ENABLED
                elif state == 'Disabled':
                    service_status.enablement_status = EnablementStatus.DISABLED

        except Exception as e:
            self.logger.warning('Error getting service status: %s', e)

        self.logger.info('Service %s status: %s', self.service_name, service_status)
        return service_status

    @property
    def version(self) -> Optional[Version]:
        self.logger.debug('Getting version for service: %s', self.service_name)
        
        try:
            result = subprocess.run(
                ['cmd', '/c', 'schtasks', '/Query', '/TN', self.service_name, '/FO', 'LIST', '/V'],
                capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                self.logger.warning('Failed to get service details: %s', result.stderr)
                return None
            
            output = result.stdout
            comment_match = re.search(r'Comment:(.*?)(?=\w+:|\Z)', output, re.DOTALL)
            
            if not comment_match:
                self.logger.warning('Description not found in task details')
                return None
            
            full_comment = comment_match.group(1).strip()
            self.logger.debug('Full service description: %s', full_comment)
            
            version_match = re.search(r'version=(\d+\.\d+\.\d+)', full_comment)
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
        
        xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Service {service_name}
version={version}</Description>
    <URI>\\{service_name}</URI>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{userid}</UserId>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{user_sid}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <Duration>PT10M</Duration>
      <WaitTimeout>PT1H</WaitTimeout>
      <StopOnIdleEnd>true</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>10</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>wscript.exe</Command>
      <Arguments>{vbs_path}</Arguments>
    </Exec>
  </Actions>
</Task>
'''
        file_path = Path(extract_dir) / 'task.xml'
        file_path.write_text(xml, encoding='utf-16')
        return file_path


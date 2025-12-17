"""Tests for service installation and uninstallation lifecycle.

Based on Flutter tests: "Uninstallation from different states" group.
"""

import platform
import time

import pytest

from etiket_service_manager import (
    InstallationStatus,
    EnablementStatus,
    RunningStatus,
    ServiceAlreadyInstalledError,
    ServiceNotInstalledError,
)
from conftest import (
    TEST_SERVICE_VERSION,
    verify_service_healthy,
    verify_service_dead,
)


class TestServiceLifecycle:
    """Tests for service lifecycle: install, reinstall, uninstall."""

    def test_install_reinstall_uninstall_cycle(
        self,
        service_manager,
        test_service_path,
    ):
        """Install, attempt reinstall (error), uninstall, attempt uninstall again (error).
        
        Mirrors Flutter test: 'Install, reinstall (error), uninstall, uninstall again (error)'
        """
        # Install the service
        service_manager.install(
            program_arguments=[str(test_service_path)],
            version=TEST_SERVICE_VERSION,
            raise_if_already_installed=True,
        )
        
        status = service_manager.status
        assert status.installation_status == InstallationStatus.INSTALLED
        assert status.running_status == RunningStatus.RUNNING
        assert status.enablement_status == EnablementStatus.ENABLED
        
        # Verify healthy
        assert verify_service_healthy()

        # Try to install again with raise_if_already_installed=True, should throw
        with pytest.raises(ServiceAlreadyInstalledError):
            service_manager.install(
                program_arguments=[str(test_service_path)],
                version=TEST_SERVICE_VERSION,
                raise_if_already_installed=True,
            )
        
        # Status should still be installed
        status = service_manager.status
        assert status.installation_status == InstallationStatus.INSTALLED
        
        # Uninstall
        service_manager.uninstall(raise_if_not_installed=True)
        
        status = service_manager.status
        assert status.installation_status == InstallationStatus.NOT_INSTALLED
        
        # Verify dead
        assert verify_service_dead()
        
        # Try to uninstall again with raise_if_not_installed=True, should throw
        with pytest.raises(ServiceNotInstalledError):
            service_manager.uninstall(raise_if_not_installed=True)
        
        # Status should still be not installed
        status = service_manager.status
        assert status.installation_status == InstallationStatus.NOT_INSTALLED

    def test_install_stop_disable_uninstall(
        self,
        installed_service,
    ):
        """Install, stop, disable, then uninstall.
        
        Mirrors Flutter test: 'Install, stop and disable, uninstall'
        """
        status = installed_service.status
        assert status.installation_status == InstallationStatus.INSTALLED
        
        # Verify healthy
        assert verify_service_healthy()

        # Stop and disable
        installed_service.stop()
        installed_service.disable()
        
        status = installed_service.status
        assert status.running_status == RunningStatus.NOT_RUNNING
        assert status.enablement_status == EnablementStatus.DISABLED
        
        # Verify dead
        assert verify_service_dead()
        
        # Uninstall
        installed_service.uninstall()
        
        status = installed_service.status
        assert status.installation_status == InstallationStatus.NOT_INSTALLED

    def test_install_stop_only_uninstall(
        self,
        installed_service,
    ):
        """Install, only stop (still enabled), then uninstall.
        
        Mirrors Flutter test: 'Install, only stop (still enabled), uninstall'
        """
        status = installed_service.status
        assert status.installation_status == InstallationStatus.INSTALLED
        
        # Verify healthy
        assert verify_service_healthy()

        # Only stop (stays enabled)
        installed_service.stop()
        
        status = installed_service.status
        assert status.running_status == RunningStatus.NOT_RUNNING
        assert status.enablement_status == EnablementStatus.ENABLED
        
        # Verify dead
        assert verify_service_dead()
        
        # Uninstall
        installed_service.uninstall()
        
        status = installed_service.status
        assert status.installation_status == InstallationStatus.NOT_INSTALLED
        assert status.enablement_status == EnablementStatus.DISABLED
        assert status.running_status == RunningStatus.NOT_RUNNING

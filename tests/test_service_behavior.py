"""Tests for service behavior after installation.

Based on Flutter tests: "Service behavior tests" group.
"""

import platform
import time

import pytest

from etiket_service_manager import (
    InstallationStatus,
    EnablementStatus,
    RunningStatus,
)
from conftest import (
    TEST_SERVICE_VERSION,
    wait_for_service_state,
    verify_service_healthy,
    verify_service_dead,
)


class TestServiceBehavior:
    """Tests for service behavior: start, stop, enable, disable."""

    def test_service_installed_and_running(
        self,
        installed_service,
    ):
        """Verify service starts in running state after install.
        
        Mirrors Flutter test: 'Service is installed and set to running'
        """
        status = installed_service.status
        assert status.installation_status == InstallationStatus.INSTALLED
        assert status.running_status == RunningStatus.RUNNING
        assert status.enablement_status == EnablementStatus.ENABLED
        
        # Verify healthy
        assert verify_service_healthy()

    def test_disable_service(
        self,
        installed_service,
    ):
        """Disable service and verify status.
        
        Mirrors Flutter test: 'Disable service, check status'
        """
        installed_service.disable()
        
        status = installed_service.status
        assert status.installation_status == InstallationStatus.INSTALLED
        assert status.running_status == RunningStatus.NOT_RUNNING
        assert status.enablement_status == EnablementStatus.DISABLED
        
        # Verify dead
        assert verify_service_dead()

    def test_start_after_disable(
        self,
        installed_service,
    ):
        """Start service after disable and verify status.
        
        Mirrors Flutter test: 'Start service after disable, check status'
        """
        installed_service.disable()
        verify_service_dead()
        
        installed_service.start()
        
        # Wait for service to start
        wait_for_service_state(installed_service, expected_running=True)
        
        # Verify healthy
        assert verify_service_healthy()
        
        status = installed_service.status
        assert status.installation_status == InstallationStatus.INSTALLED
        assert status.running_status == RunningStatus.RUNNING
        assert status.enablement_status == EnablementStatus.ENABLED

    def test_stop_service(
        self,
        installed_service,
    ):
        """Stop service and verify status.
        
        Mirrors Flutter test: 'Stop service, check status'
        """
        installed_service.stop()
        
        status = installed_service.status
        assert status.installation_status == InstallationStatus.INSTALLED
        assert status.running_status == RunningStatus.NOT_RUNNING
        assert status.enablement_status == EnablementStatus.ENABLED
        
        # Verify dead
        assert verify_service_dead()

    def test_stop_start_cycle(
        self,
        installed_service,
    ):
        """Stop and start 5 times, checking status each time.
        
        Mirrors Flutter test: 'Stop and start 5 times, check status each time'
        
        Note: On Linux, systemd has rate limiting (5 restarts in 10 seconds by default),
        so we add a delay between cycles.
        """
        # Verify initial health
        assert verify_service_healthy()

        for i in range(5):
            installed_service.stop()
            
            status = installed_service.status
            assert status.running_status == RunningStatus.NOT_RUNNING, f"Cycle {i}: stop failed"
            
            # Verify dead
            assert verify_service_dead(), f"Cycle {i}: service not dead after stop"

            installed_service.start()
            
            # Wait for service to start
            wait_for_service_state(installed_service, expected_running=True)
            
            # Verify healthy
            assert verify_service_healthy(), f"Cycle {i}: service not healthy after restart"
            
            status = installed_service.status
            assert status.running_status == RunningStatus.RUNNING, f"Cycle {i}: start failed"
            
            # Add delay on Linux to avoid systemd rate limiting
            if platform.system() == "Linux":
                time.sleep(2)

    def test_stop_and_disable(
        self,
        installed_service,
    ):
        """Stop then disable and verify status.
        
        Mirrors Flutter test: 'Stop and disable service, check status'
        """
        installed_service.stop()
        installed_service.disable()
        
        status = installed_service.status
        assert status.installation_status == InstallationStatus.INSTALLED
        assert status.running_status == RunningStatus.NOT_RUNNING
        assert status.enablement_status == EnablementStatus.DISABLED
        
        # Verify dead
        assert verify_service_dead()

    def test_version_correct(
        self,
        installed_service,
    ):
        """Verify version is correctly reported.
        
        Mirrors Flutter test: 'Check if version is correct'
        """
        # Optional: verify service is running to read version (though some backends might read from file)
        verify_service_healthy()

        version = installed_service.version
        assert version is not None
        assert str(version) == str(TEST_SERVICE_VERSION)

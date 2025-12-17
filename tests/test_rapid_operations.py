"""Tests for rapid sequential operations.

These tests verify that the service manager handles quick operations
correctly. Note that only single-threaded sequential operations need
to be supported in practice.
"""

import time

import pytest

from etiket_service_manager import (
    InstallationStatus,
    RunningStatus,
)
from conftest import (
    TEST_SERVICE_VERSION,
    wait_for_service_state,
    verify_service_healthy,
    verify_service_dead,
)


class TestRapidOperations:
    """Tests for rapid sequential operations."""

    def test_rapid_install_uninstall(
        self,
        service_manager,
        test_service_path,
    ):
        """Rapid install/uninstall cycles work correctly."""
        for i in range(3):
            # Install
            service_manager.install(
                program_arguments=[str(test_service_path)],
                version=TEST_SERVICE_VERSION,
            )
            
            status = service_manager.status
            assert status.installation_status == InstallationStatus.INSTALLED, (
                f"Cycle {i}: install failed"
            )
            
            # Verify healthy
            assert verify_service_healthy(), f"Cycle {i}: service not healthy after install"
            
            # Uninstall
            service_manager.uninstall()
            
            status = service_manager.status
            assert status.installation_status == InstallationStatus.NOT_INSTALLED, (
                f"Cycle {i}: uninstall failed"
            )
            
            # Verify dead
            assert verify_service_dead(), f"Cycle {i}: service not dead after uninstall"

    def test_rapid_enable_disable(
        self,
        installed_service,
    ):
        """Rapid enable/disable cycles maintain correct status."""
        # Initial verification
        assert verify_service_healthy(), "Service not healthy initially"

        for i in range(5):
            # Disable
            installed_service.disable()
            
            status = installed_service.status
            assert status.running_status == RunningStatus.NOT_RUNNING, (
                f"Cycle {i}: disable didn't stop service"
            )
            
            # Verify dead
            assert verify_service_dead(), f"Cycle {i}: service not dead after disable"

            # Enable and start
            installed_service.start()
            
            # Wait for service to start
            wait_for_service_state(installed_service, expected_running=True, timeout=10)
            
            # Verify healthy
            assert verify_service_healthy(), f"Cycle {i}: service not healthy after restart"
            
            status = installed_service.status
            assert status.running_status == RunningStatus.RUNNING, (
                f"Cycle {i}: start failed"
            )

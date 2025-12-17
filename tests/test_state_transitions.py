"""Tests for service state transitions and status consistency.

Based on Flutter tests: "Error handling tests" group.

Note: This library does not raise exceptions for redundant operations (e.g., starting
an already running service) unless explicitly requested via raise_if_* parameters.
These tests verify that the correct status is maintained after such operations.
"""

import pytest

from etiket_service_manager import (
    InstallationStatus,
    EnablementStatus,
    RunningStatus,
)
from conftest import wait_for_service_state


class TestStateTransitions:
    """Tests for service state transitions and status consistency."""

    def test_start_running_maintains_status(
        self,
        installed_service,
    ):
        """Starting an already running service maintains correct status.
        
        Mirrors Flutter test: 'Starting or enabling an already started/enabled service causes an error'
        Note: In this Python version, no error is raised unless raise_if_already_running=True.
        """
        # Service should already be started and enabled
        status = installed_service.status
        assert status.running_status == RunningStatus.RUNNING
        assert status.enablement_status == EnablementStatus.ENABLED
        
        # Starting again should not change status
        installed_service.start()  # No raise_if_already_running
        
        status = installed_service.status
        assert status.running_status == RunningStatus.RUNNING
        assert status.enablement_status == EnablementStatus.ENABLED

    def test_enable_enabled_maintains_status(
        self,
        installed_service,
    ):
        """Enabling an already enabled service maintains correct status."""
        # Service should already be enabled
        status = installed_service.status
        assert status.enablement_status == EnablementStatus.ENABLED
        
        # Enabling again should not change status
        installed_service.enable()  # No raise_if_already_enabled
        
        status = installed_service.status
        assert status.enablement_status == EnablementStatus.ENABLED

    def test_stop_stopped_maintains_status(
        self,
        installed_service,
    ):
        """Stopping an already stopped service maintains correct status.
        
        Mirrors Flutter test: 'Stopping an already stopped service causes an error, but disabling does not'
        """
        # Stop the service first
        installed_service.stop()
        
        status = installed_service.status
        assert status.running_status == RunningStatus.NOT_RUNNING
        assert status.enablement_status == EnablementStatus.ENABLED
        
        # Stopping again should maintain status
        installed_service.stop()  # No raise_if_already_stopped
        
        status = installed_service.status
        assert status.running_status == RunningStatus.NOT_RUNNING

    def test_disable_disabled_maintains_status(
        self,
        installed_service,
    ):
        """Disabling an already disabled service maintains correct status."""
        # Disable the service first
        installed_service.disable()
        
        status = installed_service.status
        assert status.enablement_status == EnablementStatus.DISABLED
        
        # Disabling again should maintain status
        installed_service.disable()  # No raise_if_already_disabled
        
        status = installed_service.status
        assert status.enablement_status == EnablementStatus.DISABLED

    def test_start_disabled_works(
        self,
        installed_service,
    ):
        """Starting a disabled service works correctly.
        
        Mirrors Flutter test: 'Starting a disabled service works without error'
        """
        # Stop and disable the service first
        installed_service.stop()
        installed_service.disable()
        
        status = installed_service.status
        assert status.running_status == RunningStatus.NOT_RUNNING
        assert status.enablement_status == EnablementStatus.DISABLED
        
        # Starting should work without error and enable the service
        installed_service.start()
        
        # Wait for service to start
        wait_for_service_state(installed_service, expected_running=True)
        
        status = installed_service.status
        assert status.running_status == RunningStatus.RUNNING
        assert status.enablement_status == EnablementStatus.ENABLED

    def test_stopped_and_disabled_operations(
        self,
        installed_service,
    ):
        """Operations on a stopped and disabled service maintain correct status.
        
        Mirrors Flutter test: 'Stopping or disabling an already stopped and disabled service causes an error'
        """
        # Stop and disable the service first
        installed_service.stop()
        installed_service.disable()
        
        status = installed_service.status
        assert status.running_status == RunningStatus.NOT_RUNNING
        assert status.enablement_status == EnablementStatus.DISABLED
        
        # Stopping again should maintain status
        installed_service.stop()
        
        status = installed_service.status
        assert status.running_status == RunningStatus.NOT_RUNNING
        
        # Disabling again should maintain status
        installed_service.disable()
        
        status = installed_service.status
        assert status.enablement_status == EnablementStatus.DISABLED

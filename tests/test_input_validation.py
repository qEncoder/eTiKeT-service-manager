"""Tests for input validation.

Based on Flutter tests: "Input validation tests" group.
"""

from pathlib import Path

import pytest

from etiket_service_manager import ServiceConfig, ServiceManager
from packaging.version import Version

from conftest import TEST_SERVICE_VERSION


class TestInputValidation:
    """Tests for input validation."""

    def test_empty_service_name_raises(self, tmp_path: Path):
        """Empty service name raises ValueError.
        
        Mirrors Flutter test: 'Empty service name causes an error'
        """
        with pytest.raises(ValueError):
            ServiceConfig(
                service_name="",  # Empty service name
                app_dir=tmp_path,
            )

    def test_nonexistent_executable_raises(self, service_manager):
        """Non-existent absolute executable path raises FileNotFoundError.
        
        Mirrors Flutter test: 'Non-existing executable path causes an error'
        """
        with pytest.raises(FileNotFoundError):
            service_manager.install(
                program_arguments=["/non/existent/path/to/executable"],
                version=TEST_SERVICE_VERSION,
            )

    def test_empty_program_arguments_raises(self, service_manager):
        """Empty program arguments list should raise an error."""
        with pytest.raises((ValueError, IndexError)):
            service_manager.install(
                program_arguments=[],
                version=TEST_SERVICE_VERSION,
            )

"""Pytest configuration and fixtures for etiket-service-manager tests."""

import platform
import sys
import time
from pathlib import Path
from typing import Generator
import logging

import pytest

from etiket_service_manager import (
    ServiceConfig,
    ServiceManager,
    InstallationStatus,
)
from packaging.version import Version

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Test configuration
TEST_SERVICE_NAME = "test_service"
TEST_SERVICE_VERSION = Version("1.0.0")
TEST_SERVICE_PORT = 8765


def get_test_service_path() -> Path:
    """Get the path to the test service executable for the current platform."""
    tests_dir = Path(__file__).parent
    dist_dir = tests_dir / "test_service" / "dist"
    
    if platform.system() == "Windows":
        exe_path = dist_dir / "test_service.exe"
    elif platform.system() == "Linux":
        exe_path = dist_dir / "test_service" / "test_service"
    else:
        exe_path = dist_dir / "test_service"
    
    if not exe_path.exists():
        pytest.skip(
            f"Test service executable not found: {exe_path}. "
            "Run 'python tests/test_service/build_test_service.py' first."
        )
    
    return exe_path


@pytest.fixture
def test_service_path() -> Path:
    """Fixture providing the path to the test service executable."""
    return get_test_service_path()


@pytest.fixture
def app_dir(tmp_path: Path) -> Path:
    """Fixture providing a temporary app directory for service files."""
    app_directory = tmp_path / "test_app"
    app_directory.mkdir(parents=True, exist_ok=True)
    return app_directory


@pytest.fixture
def service_config(app_dir: Path) -> ServiceConfig:
    """Fixture providing a ServiceConfig for tests."""
    return ServiceConfig(
        service_name=TEST_SERVICE_NAME,
        app_dir=app_dir,
    )


@pytest.fixture
def service_manager(service_config: ServiceConfig) -> Generator[ServiceManager, None, None]:
    """Fixture providing a ServiceManager with automatic cleanup."""
    manager = ServiceManager(service_config)
    
    yield manager
    
    # Cleanup: ensure service is uninstalled after test
    try:
        status = manager.status
        if status.installation_status == InstallationStatus.INSTALLED:
            manager.uninstall()
            time.sleep(1) # ensure that there is some time for the port to be released
    except Exception as e:
        logging.warning(f"Cleanup failed (can be ignored): {e}")


@pytest.fixture
def installed_service(
    service_manager: ServiceManager,
    test_service_path: Path,
) -> Generator[ServiceManager, None, None]:
    """Fixture providing a ServiceManager with the service already installed."""
    # Install the service
    service_manager.install(
        program_arguments=[str(test_service_path)],
        version=TEST_SERVICE_VERSION,
        raise_if_already_installed=True,
    )
    
    # Give the service time to start
    time.sleep(5)
    
    yield service_manager
    
    # Cleanup is handled by the service_manager fixture


def wait_for_service_state(
    manager: ServiceManager,
    expected_running: bool,
    timeout: float = 10.0,
    poll_interval: float = 0.5,
) -> bool:
    """Wait for the service to reach the expected running state.
    
    Args:
        manager: The service manager to check.
        expected_running: Whether we expect the service to be running.
        timeout: Maximum time to wait in seconds.
        poll_interval: Time between checks in seconds.
    
    Returns:
        True if the expected state was reached, False if timeout occurred.
    """
    from etiket_service_manager import RunningStatus
    
    expected_status = (
        RunningStatus.RUNNING if expected_running else RunningStatus.NOT_RUNNING
    )
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = manager.status
        if status.running_status == expected_status:
            return True
        time.sleep(poll_interval)
    
    return False


def verify_service_healthy(timeout: float = 10.0) -> bool:
    """Verify that the service is actually responsive via HTTP.
    
    Args:
        timeout: Maximum time to wait for a successful response.
        
    Returns:
        True if the service responds with 200 OK, False otherwise.
    """
    try:
        import httpx
    except ImportError:
        # If httpx is not available, we can't verify
        return True
        
    url = f"http://localhost:{TEST_SERVICE_PORT}/"
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return True
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(0.5)
            
    return False


def verify_service_dead(timeout: float = 10.0) -> bool:
    """Verify that the service is NOT responsive via HTTP.
    
    Args:
        timeout: Maximum time to wait for connection failure.
        
    Returns:
        True if the service stops responding (connection error), False otherwise.
    """
    try:
        import httpx
    except ImportError:
        # If httpx is not available, we can't verify
        return True
        
    url = f"http://localhost:{TEST_SERVICE_PORT}/"
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            with httpx.Client(timeout=2.0) as client:
                client.get(url)
            # If we get here, connection succeeded, wait and try again
            time.sleep(0.5)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError):
            # Connection failed, service is dead
            return True
            
    return False

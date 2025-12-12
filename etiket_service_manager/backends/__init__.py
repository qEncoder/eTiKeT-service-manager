"""Platform-specific service manager backends."""

from etiket_service_manager.backends.base import ServiceManagerBackend
from etiket_service_manager.backends.linux import LinuxServiceManager
from etiket_service_manager.backends.macos import MacOSServiceManager
from etiket_service_manager.backends.windows import WindowsServiceManager

__all__ = [
    'ServiceManagerBackend',
    'LinuxServiceManager',
    'MacOSServiceManager',
    'WindowsServiceManager',
]


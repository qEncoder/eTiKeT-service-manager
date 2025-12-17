"""eTiKeT Sync Agent service."""

from etiket_service_manager import ServiceManager, ServiceConfig
from etiket_service_manager.services._paths import ensure_service_dir

SERVICE_NAME = "etiket_sync_agent"


def get_service() -> ServiceManager:
    """Get the Sync Agent service manager."""
    config = ServiceConfig(
        service_name=SERVICE_NAME,
        app_dir=ensure_service_dir(),
    )
    return ServiceManager(config)


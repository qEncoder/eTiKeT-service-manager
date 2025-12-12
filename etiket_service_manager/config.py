"""Service configuration."""

from pathlib import Path


class ServiceConfig:
    """Configuration for a service."""
    
    def __init__(self, service_name: str, app_dir: Path):
        """
        Initialize service configuration.
        
        Args:
            service_name: Name of the service.
            app_dir: Directory where the service application resides.
        
        Raises:
            ValueError: If service_name is empty.
        """
        if not service_name:
            raise ValueError('Service name cannot be empty')
        self.service_name = service_name
        self.app_dir = app_dir


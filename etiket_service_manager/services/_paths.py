"""Platform-specific paths for services."""

import os
import platform
from pathlib import Path


def get_service_dir() -> Path:
    """Get the platform-specific directory for service files."""
    system = platform.system()
    
    if system == 'Darwin':
        path = Path.home() / "Library" / "Application Support" / "qharbor"
    elif system == 'Linux':
        xdg_data = os.environ.get('XDG_DATA_HOME', str(Path.home() / ".local" / "share"))
        path = Path(xdg_data) / "qharbor"
    elif system == 'Windows':
        path = Path(os.environ['LOCALAPPDATA']) / "qharbor"
    else:
        raise ValueError(f"Unsupported platform: {system}")
    
    return path


def ensure_service_dir() -> Path:
    """Get the service directory, creating it if it doesn't exist."""
    path = get_service_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


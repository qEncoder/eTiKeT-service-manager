# Service Manager

A cross-platform library for installing and managing services on Windows, macOS, and Linux.

## Overview

The Service Manager library provides a unified interface for managing system services across different operating systems. It follows standard service management conventions, allowing you to:

* Install/uninstall services
* Enable/disable services at boot time
* Start/stop running services
* Query service status

It creates user-level services (not system-wide root services), which means:
* **Linux**: User systemd services (`systemctl --user`)
* **macOS**: LaunchAgents (`~/Library/LaunchAgents`)
* **Windows**: Scheduled Tasks (running on user login)

## Installation

```bash
pip install etiket-service-manager
```

## Pre-configured Services

This library includes pre-configured service definitions for the QHarbor application suite. These helper functions automatically set up the correct paths and naming conventions for QHarbor's sync components.

```python
from etiket_service_manager.services import sync_agent, sync_api

# Get the manager for the Sync Agent
agent_manager = sync_agent.get_service()
agent_manager.status  # Check status

# Get the manager for the Sync API
api_manager = sync_api.get_service()
api_manager.status    # Check status
```

These services are configured to use standard system locations for data and configuration:
- **macOS**: `~/Library/Application Support/qharbor`
- **Linux**: `~/.local/share/qharbor` (or `$XDG_DATA_HOME/qharbor`)
- **Windows**: `%LOCALAPPDATA%\qharbor`

## Actions and Behaviors

The following table describes each action, its expected behavior, possible errors, and resulting service states:

| Action | Description | Possible Errors | Expected Status After Action |
|--------|-------------|----------------|---------------------------|
| **install** | Installs, enables, and starts the service | `ServiceAlreadyInstalled`, `ServiceOperationError` | installed=True, enabled=True, running=True |
| **enable** | Enables the service to start automatically at boot | `ServiceAlreadyEnabled`, `ServiceOperationError` | installed=True, enabled=True, running=unchanged |
| **start** | Starts the service | `ServiceAlreadyStarted`, `ServiceOperationError` | installed=True, enabled=unchanged, running=True |
| **stop** | Stops the service | `ServiceAlreadyStopped`, `ServiceOperationError` | installed=True, enabled=unchanged, running=False |
| **disable** | Disables the service (prevents starting at boot) | `ServiceAlreadyDisabled`, `ServiceOperationError` | installed=True, enabled=False, running=False |
| **uninstall** | Uninstalls the service | `ServiceAlreadyUnInstalled`, `ServiceOperationError` | installed=False, enabled=False, running=False |

## Configuring the Service Manager

To use the Service Manager for your own applications, you need to create a `ServiceConfig` object.

```python
from pathlib import Path
from etiket_service_manager import ServiceConfig, ServiceManager

config = ServiceConfig(
    service_name="my_service",      # Name of the service
    app_dir=Path("/path/to/app")    # Directory for service files/logs
)

# Initialize service manager
manager = ServiceManager(config)
```

## Example Usage

```python
from etiket_service_manager import ServiceManager, ServiceConfig
from packaging.version import Version
from pathlib import Path

def main():
    # 1. Configure
    config = ServiceConfig(
        service_name="my_service", 
        app_dir=Path.home() / ".my_service"
    )
    manager = ServiceManager(config)
    
    # 2. Install
    # The command to start your service (must be absolute path for executable)
    cmd = ["/path/to/venv/bin/python", "-m", "my_service"]
    
    manager.install(
        program_arguments=cmd,
        version=Version("1.0.0"),
        raise_if_already_installed=True
    )
    
    # 3. Check status
    print(f"Service status: {manager.status}")
    
    # 4. Stop
    manager.stop()
    
    # 5. Disable automatic startup
    manager.disable()
    
    # 6. Uninstall when no longer needed
    manager.uninstall()

if __name__ == "__main__":
    main()
```

---

# Platform Specific Details

## Windows Services

This application is implemented as a **Scheduled Task** rather than a Windows service. A scheduled task can run without administrator permissions, unlike Windows services.

The scheduled task:
- Runs as a background process with `wscript` (hidden window).
- Starts automatically when the user logs in.
- Provides support for process recovery when it terminates unexpectedly.

### Requirements
- The service name is used as the Task Name.
- Tasks are created with "LeastPrivilege" run level, so no UAC prompt is needed.

## macOS Services

This document outlines the process for creating and managing macOS services using `launchctl`. These services run in the GUI session of the logged-in user (LaunchAgents).

### Installation Locations
- **Service configuration file**: `~/Library/LaunchAgents/com.qharbor.{service_name}.plist`
- **Logs**: `{app_dir}/{service_name}_logs/`

> [!IMPORTANT]
> The service is configured with `WorkingDirectory` set to the `app_dir`. If your application uses relative paths for resources or imports, or if you register the service with a relative path to the executable, the application **must** be located inside `app_dir` for it to work correctly.

The service definition (plist) includes:
- `KeepAlive`: True (system attempts to restart it if it crashes)
- `RunAtLoad`: True (starts immediately upon load/login)
- `ThrottleInterval`: 60 seconds

## Linux Services

Service in Linux are implemented using **systemd** user services. This is a robust system that works very well for user-level background processes.

### Locations
- **Configuration**: The systemd user unit file (`{service_name}.service`) is created in `~/.config/systemd/user/`.
- **Logs**: Managed by systemd. View logs using:
  ```bash
  journalctl --user -u {service_name}
  ```
  - Use `-f` to follow logs in real-time.
  - Use `-e` to jump to the end.
- **Application Binary**: The application executable should be in a stable, user-accessible location.
  - Recommended: `~/.local/bin/` for standalone binaries.
  - Note: Self-contained application directories often reside in `~/.local/share/`.
  - **Important**: Always provide the **absolute path** to the executable when installing the service.

### Behavior
- Uses `systemctl --user` commands to manage the service.
- defined as `Type=simple`.
- Configured with `Restart=always` and a 5-second delay to ensure reliability.


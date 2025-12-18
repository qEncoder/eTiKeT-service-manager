"""Linux systemd service file templates."""

SYSTEMD_SERVICE_TEMPLATE = """[Unit]
Description={service_name} service
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
WorkingDirectory={working_directory}
Restart=always
RestartSec=5

Environment="VERSION={version}"

[Install]
WantedBy=default.target
"""

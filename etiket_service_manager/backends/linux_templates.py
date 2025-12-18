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
StandardOutput=append:{stdout_log}
StandardError=append:{stderr_log}
Environment="VERSION={version}"

[Install]
WantedBy=default.target
"""

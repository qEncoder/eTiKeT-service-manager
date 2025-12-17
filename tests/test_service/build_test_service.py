#!/usr/bin/env python3
"""Build script for creating the test service executable.

This script uses PyInstaller to build a single-file executable
for the current platform.

Usage:
    python build_test_service.py
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Build the test service executable."""
    script_dir = Path(__file__).parent
    source_file = script_dir / "test_service.py"
    
    if not source_file.exists():
        print(f"Error: Source file not found: {source_file}")
        sys.exit(1)
    
    print(f"Building test service for {sys.platform}...")
    
    # Determine output name
    exe_name = "test_service.exe" if sys.platform == "win32" else "test_service"
    
    # Run PyInstaller directly - let it auto-generate the spec
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",
            "--clean",
            "--noconfirm",
            "--name", exe_name.replace(".exe", ""),
            # Exclude heavy packages we don't need
            "--exclude-module", "PyQt5",
            "--exclude-module", "PyQt6",
            "--exclude-module", "PySide2",
            "--exclude-module", "PySide6",
            "--exclude-module", "IPython",
            "--exclude-module", "matplotlib",
            "--exclude-module", "numpy",
            "--exclude-module", "pandas",
            "--exclude-module", "scipy",
            "--exclude-module", "PIL",
            "--exclude-module", "tkinter",
            "--exclude-module", "sphinx",
            "--exclude-module", "docutils",
            "--exclude-module", "babel",
            "--exclude-module", "zmq",
            str(source_file),
        ],
        cwd=script_dir,
    )
    
    if result.returncode != 0:
        print("Error: PyInstaller build failed")
        sys.exit(1)
    
    output_path = script_dir / "dist" / exe_name
    
    if output_path.exists():
        print(f"Success! Executable created: {output_path}")
        print(f"Size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")
    else:
        print(f"Warning: Expected output not found: {output_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()

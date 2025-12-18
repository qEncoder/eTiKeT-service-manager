"""Setup script for Cython compilation of etiket_service_manager."""

import glob
import os
from pathlib import Path

from Cython.Build import cythonize
from setuptools import setup
from setuptools.extension import Extension
from setuptools.command.build_py import build_py as build_py_orig

# Base directory for source files
SRC_DIR = Path("etiket_service_manager")

# Find all .py files to compile
py_files = glob.glob(str(SRC_DIR / "**/*.py"), recursive=True)

# Files/directories to EXCLUDE from compilation (keep as pure Python)
# - __init__.py files: needed for package imports
# - __pycache__: not source files
EXCLUDE_PATTERNS = [
    "__init__.py",
    "__pycache__",
]

# Check if we should build pure Python wheel (skip compilation)
BUILD_PURE = os.environ.get("ETIKET_BUILD_PURE", "0") == "1"

if BUILD_PURE:
    extensions = []
    cmdclass = {}
else:
    extensions = []
    compiled_modules = set()

    for filepath in py_files:
        # Normalize path separators for consistent exclusion matching
        normalized_path = filepath.replace("\\", "/")
        
        # Skip excluded files
        if any(pattern in normalized_path for pattern in EXCLUDE_PATTERNS):
            continue

        # Convert file path to module name using Path for cross-platform support
        # e.g., "etiket_service_manager/backends/linux.py" -> "etiket_service_manager.backends.linux"
        path_obj = Path(filepath)
        module_name = ".".join(path_obj.with_suffix("").parts)

        extensions.append(
            Extension(
                name=module_name,
                sources=[filepath],
            )
        )
        compiled_modules.add(module_name)

    # Custom build_py to exclude .py files that are compiled
    class build_py(build_py_orig):
        def find_package_modules(self, package, package_dir):
            modules = super().find_package_modules(package, package_dir)
            # Filter out .py files that have been compiled
            return [
                (pkg, mod, file)
                for (pkg, mod, file) in modules
                if f"{pkg}.{mod}" not in compiled_modules
            ]
    
    cmdclass = {"build_py": build_py}


# Only run cythonize if we have extensions
if extensions:
    ext_modules = cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "embedsignature": True,  # Preserves function signatures in .so
        },
        # Don't generate .html annotation files
        annotate=False,
    )
else:
    ext_modules = []

setup(
    ext_modules=ext_modules,
    cmdclass=cmdclass,
)

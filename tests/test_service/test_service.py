"""Simple test service for unit testing etiket-service-manager.

This FastAPI application is designed to be compiled with PyInstaller and
used as a test service for verifying service management functionality.
"""

import os
from fastapi import FastAPI
import uvicorn

# Version of the test service
VERSION = "1.0.0"

# Port to run on (can be overridden via environment variable)
PORT = int(os.environ.get("TEST_SERVICE_PORT", "8765"))

app = FastAPI(title="Test Service", version=VERSION)


@app.get("/")
def hello():
    """Simple hello world endpoint to verify service is running."""
    return {"message": "Hello World", "version": VERSION}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

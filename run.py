"""
Application Launcher.

Starts the Uvicorn ASGI server to serve the FastAPI backend.
Usage:
    python run.py
"""

import os
import sys
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    default_host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"
    host = os.environ.get("HOST", default_host)

    print("=" * 80)
    print("Starting Cybercrime Predictive Analytics Server...")
    print(f"Interactive Documentation: http://{host}:{port}/docs")
    print(f"REST API Root:             http://{host}:{port}/api")
    print("=" * 80)
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=False)


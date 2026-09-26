"""
Application Launcher.

Starts the Uvicorn ASGI server to serve the FastAPI backend.
Usage:
    python run.py
"""

import sys
import uvicorn

if __name__ == "__main__":
    print("=" * 80)
    print("Starting Cybercrime Predictive Analytics Server...")
    print("Interactive Documentation: http://127.0.0.1:8000/docs")
    print("REST API Root:             http://127.0.0.1:8000/api")
    print("=" * 80)
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)

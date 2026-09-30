"""
Vercel Serverless Function Entry Point for MeghDrishti
Exposes the FastAPI ASGI application instance for Vercel serverless routing.
"""
import sys
import os

# Ensure the project root is in sys.path so modules like config, database, nwp, ml, schemas, services import cleanly
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from main import app  # noqa: E402

# ASGI handler recognized by Vercel's Python runtime
app = app

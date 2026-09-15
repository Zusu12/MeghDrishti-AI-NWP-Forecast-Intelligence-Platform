import sys
import os

# Add repository root directory to sys.path so all application modules resolve
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from main import app

# Export FastAPI instance for Vercel Serverless Function
app = app

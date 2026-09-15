"""conftest.py — ensure project root is on sys.path before test collection"""
import sys
import os

# Absolute path to project root — needed for Python 3.14 venv
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

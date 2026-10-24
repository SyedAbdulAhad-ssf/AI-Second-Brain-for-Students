"""Vercel Python serverless entry point.

The Vercel route configuration sends API and frontend requests here; Flask
serves /api/* endpoints, files from public/, and the root login page.
"""
from app import app

# Vercel's Python runtime discovers this WSGI application.

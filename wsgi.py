"""WSGI entry point for production server"""

import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.config.settings import config

# Get environment
env = os.getenv('FLASK_ENV', 'production')

# Create the Flask app
app = create_app(config[env])

# This is what Gunicorn will import
if __name__ == "__main__":
    app.run()

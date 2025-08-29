#!/usr/bin/env python3
"""Development server runner"""

import os
from app import create_app
from app.config.settings import config

if __name__ == "__main__":
    # Get environment
    env = os.getenv('FLASK_ENV', 'development')
    
    # Create the Flask app
    app = create_app(config.get(env, config['default']))
    
    # Get port from environment or use default
    port = int(os.getenv('PORT', 8080))
    
    # Run the development server
    app.run(
        host='0.0.0.0',
        port=port,
        debug=(env == 'development')
    )

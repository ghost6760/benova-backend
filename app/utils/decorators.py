from functools import wraps
from flask import jsonify
import logging

logger = logging.getLogger(__name__)

def handle_errors(f):
    """Decorator for consistent error handling"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        except Exception as e:
            logger.exception(f"Unhandled error in {f.__name__}")
            return jsonify({"status": "error", "message": "Internal server error"}), 500
    return decorated_function

def require_api_key(f):
    """Decorator to require API key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request, current_app
        
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != current_app.config.get('API_KEY'):
            return jsonify({"status": "error", "message": "Invalid API key"}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def cache_result(timeout=300):
    """Decorator for caching results in Redis"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from app.services.redis_service import get_redis_client
            import json
            
            # Create cache key
            cache_key = f"cache:{f.__name__}:{str(args)}:{str(kwargs)}"
            redis_client = get_redis_client()
            
            # Check cache
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Get fresh result
            result = f(*args, **kwargs)
            
            # Cache result
            redis_client.setex(cache_key, timeout, json.dumps(result))
            
            return result
        return decorated_function
    return decorator

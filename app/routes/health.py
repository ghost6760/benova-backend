from flask import Blueprint, jsonify, current_app
from app.services.redis_service import get_redis_client
from app.services.vectorstore_service import VectorstoreService
from app.services.openai_service import OpenAIService
from app.models.conversation import ConversationManager
from app.services.multiagent_system import MultiAgentSystem
from app.utils.decorators import handle_errors
import time
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('health', __name__)

@bp.route('', methods=['GET'])
def health_check():
    """Main health check endpoint"""
    try:
        components = check_component_health()
        
        # Get statistics
        redis_client = get_redis_client()
        conversation_count = len(redis_client.keys("conversation:*"))
        document_count = len(redis_client.keys("document:*"))
        bot_status_count = len(redis_client.keys("bot_status:*"))
        
        healthy = all("error" not in str(status) for status in components.values())
        
        response_data = {
            "timestamp": time.time(),
            "components": {
                **components,
                "conversations": conversation_count,
                "documents": document_count,
                "bot_statuses": bot_status_count
            },
            "configuration": {
                "model": current_app.config['MODEL_NAME'],
                "embedding_model": current_app.config['EMBEDDING_MODEL'],
                "max_tokens": current_app.config['MAX_TOKENS'],
                "temperature": current_app.config['TEMPERATURE'],
                "max_context_messages": current_app.config['MAX_CONTEXT_MESSAGES']
            }
        }
        
        if healthy:
            return jsonify({"status": "healthy", **response_data}), 200
        else:
            return jsonify({"status": "unhealthy", **response_data}), 503
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }), 503

@bp.route('/vectorstore', methods=['GET'])
@handle_errors
def vectorstore_health():
    """Vectorstore specific health check"""
    try:
        vectorstore_service = VectorstoreService()
        health = vectorstore_service.check_health()
        
        status_code = 200 if health.get("healthy", False) else 503
        
        return jsonify({
            "status": "healthy" if health.get("healthy") else "unhealthy",
            "details": health
        }), status_code
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/multiagent', methods=['GET'])
@handle_errors
def multiagent_health():
    """Multi-agent system health check"""
    try:
        multiagent = MultiAgentSystem()
        health = multiagent.health_check()
        
        return jsonify(health), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def check_component_health():
    """Check health of all system components"""
    components = {}
    
    # Check Redis
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        components["redis"] = "connected"
    except Exception as e:
        components["redis"] = f"error: {str(e)}"
    
    # Check OpenAI
    try:
        openai_service = OpenAIService()
        openai_service.test_connection()
        components["openai"] = "connected"
    except Exception as e:
        components["openai"] = f"error: {str(e)}"
    
    # Check Vectorstore
    try:
        vectorstore_service = VectorstoreService()
        vectorstore_service.test_connection()
        components["vectorstore"] = "connected"
    except Exception as e:
        components["vectorstore"] = f"error: {str(e)}"
    
    return components

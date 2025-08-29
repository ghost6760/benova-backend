from flask import Blueprint, request, jsonify, current_app
from app.services.vectorstore_service import VectorstoreService
from app.services.redis_service import get_redis_client
from app.services.multiagent_system import MultiAgentSystem
from app.utils.decorators import handle_errors, require_api_key
from app.utils.helpers import create_success_response, create_error_response
import logging
import time  # Missing import

logger = logging.getLogger(__name__)

bp = Blueprint('admin', __name__)

@bp.route('/vectorstore/force-recovery', methods=['POST'])
@handle_errors
@require_api_key
def force_vectorstore_recovery():
    """Force vectorstore recovery"""
    try:
        vectorstore_service = VectorstoreService()
        success = vectorstore_service.force_recovery()
        
        if success:
            return create_success_response({
                "message": "Index recovery completed successfully",
                "new_health": vectorstore_service.check_health()
            })
        else:
            return create_error_response("Index recovery failed", 500)
            
    except Exception as e:
        return create_error_response(str(e), 500)

@bp.route('/vectorstore/protection-status', methods=['GET'])
@handle_errors
def protection_status():
    """Get protection status"""
    try:
        vectorstore_service = VectorstoreService()
        status = vectorstore_service.get_protection_status()
        
        return jsonify(status)
        
    except Exception as e:
        return create_error_response(str(e), 500)

@bp.route('/system/reset', methods=['POST'])
@handle_errors
@require_api_key
def reset_system():
    """Reset system caches"""
    try:
        redis_client = get_redis_client()
        
        # Clear caches
        patterns = ["processed_message:*", "bot_status:*", "cache:*"]
        cleared_count = 0
        
        for pattern in patterns:
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
                cleared_count += len(keys)
        
        logger.info(f"✅ System reset completed, cleared {cleared_count} keys")
        
        return create_success_response({
            "message": "System reset completed",
            "keys_cleared": cleared_count,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"System reset failed: {e}")
        return create_error_response("Failed to reset system", 500)

@bp.route('/status', methods=['GET'])
@handle_errors
def get_system_status():
    """Get comprehensive system status"""
    try:
        redis_client = get_redis_client()
        
        # Count various entities
        conversation_count = len(redis_client.keys("conversation:*"))
        document_count = len(redis_client.keys("document:*"))
        bot_status_keys = redis_client.keys("bot_status:*")
        processed_message_count = len(redis_client.keys("processed_message:*"))
        
        # Count active bots
        active_bots = 0
        for key in bot_status_keys:
            try:
                status_data = redis_client.hgetall(key)
                if status_data.get('active') == 'True':
                    active_bots += 1
            except:
                continue
        
        # Get multi-agent stats
        multiagent = MultiAgentSystem()
        multiagent_stats = multiagent.get_system_stats()
        
        return create_success_response({
            "timestamp": time.time(),
            "statistics": {
                "total_conversations": conversation_count,
                "active_bots": active_bots,
                "total_bot_statuses": len(bot_status_keys),
                "processed_messages": processed_message_count,
                "total_documents": document_count
            },
            "multiagent": multiagent_stats,
            "environment": {
                "chatwoot_url": current_app.config['CHATWOOT_BASE_URL'],
                "account_id": current_app.config['ACCOUNT_ID'],
                "model": current_app.config['MODEL_NAME'],
                "embedding_model": current_app.config['EMBEDDING_MODEL']
            }
        })
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return create_error_response("Failed to get status", 500)

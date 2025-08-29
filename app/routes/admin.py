from flask import Blueprint, request, jsonify, current_app
from app.services.vectorstore_service import VectorstoreService
from app.services.redis_service import get_redis_client
from app.services.multiagent_system import MultiAgentSystem
from app.utils.decorators import handle_errors, require_api_key
from app.utils.helpers import create_success_response, create_error_response
import logging
import time

logger = logging.getLogger(__name__)

bp = Blueprint('admin', __name__)

@bp.route('/vectorstore/force-recovery', methods=['POST'])
@handle_errors
@require_api_key
def force_vectorstore_recovery():
    """Force vectorstore recovery - ENHANCED from monolith"""
    try:
        from app.services.vector_auto_recovery import get_auto_recovery_instance
        
        auto_recovery = get_auto_recovery_instance()
        if not auto_recovery:
            return create_error_response("Auto-recovery system not available", 500)
        
        logger.info("Manual recovery initiated...")
        
        # Limpiar cache
        auto_recovery.health_cache = {"last_check": 0, "status": None}
        
        success = auto_recovery.reconstruct_index_from_stored_data()
        
        if success:
            return create_success_response({
                "message": "Index recovery completed successfully",
                "new_health": auto_recovery.verify_index_health()
            })
        else:
            return create_error_response("Index recovery failed", 500)
            
    except Exception as e:
        return create_error_response(str(e), 500)

@bp.route('/vectorstore/protection-status', methods=['GET'])
@handle_errors
def protection_status():
    """Get protection status - NEW from monolith"""
    try:
        from app.services.vector_auto_recovery import get_auto_recovery_instance
        
        auto_recovery = get_auto_recovery_instance()
        if not auto_recovery:
            return jsonify({
                "auto_recovery_initialized": False,
                "vectorstore_healthy": False,
                "protection_active": False,
                "error": "Auto-recovery system not initialized"
            })
        
        status = auto_recovery.get_protection_status()
        
        return jsonify({
            **status,
            "auto_recovery_initialized": True,
            "protection_active": True,
            "system_type": "modular_with_recovery"
        })
        
    except Exception as e:
        return create_error_response(str(e), 500)

@bp.route('/vectorstore/health', methods=['GET'])
@handle_errors
def vectorstore_health_check():
    """Vectorstore health check - ENHANCED from monolith"""
    try:
        from app.services.vector_auto_recovery import get_auto_recovery_instance, get_health_recommendations
        
        auto_recovery = get_auto_recovery_instance()
        if not auto_recovery:
            return jsonify({
                "status": "error",
                "message": "Auto-recovery system not initialized"
            }), 500
        
        health = auto_recovery.verify_index_health()
        status_code = 200 if health.get("healthy", False) else 503
        
        return jsonify({
            "status": "healthy" if health.get("healthy") else "unhealthy",
            "details": health,
            "auto_recovery_available": True,
            "auto_recovery_enabled": auto_recovery.auto_recovery_enabled,
            "recommendations": get_health_recommendations(health),
            "system_type": "modular_enhanced"
        }), status_code
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/system/reset', methods=['POST'])
@handle_errors
@require_api_key
def reset_system():
    """Reset system caches - ENHANCED"""
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
        
        # Clear auto-recovery cache
        try:
            from app.services.vector_auto_recovery import get_auto_recovery_instance
            auto_recovery = get_auto_recovery_instance()
            if auto_recovery:
                auto_recovery.health_cache = {"last_check": 0, "status": None}
                logger.info("Auto-recovery cache cleared")
        except Exception as e:
            logger.warning(f"Could not clear auto-recovery cache: {e}")
        
        logger.info(f"System reset completed, cleared {cleared_count} keys")
        
        return create_success_response({
            "message": "System reset completed",
            "keys_cleared": cleared_count,
            "timestamp": time.time(),
            "auto_recovery_cache_cleared": True
        })
        
    except Exception as e:
        logger.error(f"System reset failed: {e}")
        return create_error_response("Failed to reset system", 500)

@bp.route('/status', methods=['GET'])
@handle_errors
def get_system_status():
    """Get comprehensive system status - ENHANCED"""
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
        try:
            multiagent = MultiAgentSystem()
            multiagent_stats = multiagent.get_system_stats()
        except Exception as e:
            multiagent_stats = {"error": f"Could not get multiagent stats: {e}"}
        
        # Get auto-recovery status
        auto_recovery_status = {}
        try:
            from app.services.vector_auto_recovery import get_auto_recovery_instance
            auto_recovery = get_auto_recovery_instance()
            if auto_recovery:
                auto_recovery_status = {
                    "enabled": auto_recovery.auto_recovery_enabled,
                    "health_check_interval": auto_recovery.health_check_interval,
                    "last_health_check": auto_recovery.health_cache.get("last_check", 0),
                    "current_health": auto_recovery.verify_index_health()
                }
        except Exception as e:
            auto_recovery_status = {"error": f"Could not get auto-recovery status: {e}"}
        
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
            "auto_recovery": auto_recovery_status,
            "environment": {
                "chatwoot_url": current_app.config['CHATWOOT_BASE_URL'],
                "account_id": current_app.config['ACCOUNT_ID'],
                "model": current_app.config['MODEL_NAME'],
                "embedding_model": current_app.config['EMBEDDING_MODEL'],
                "auto_recovery_enabled": current_app.config.get('VECTORSTORE_AUTO_RECOVERY', True)
            },
            "system_type": "modular_enhanced"
        })
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return create_error_response("Failed to get status", 500)

@bp.route('/multimedia/test', methods=['POST'])
@handle_errors
def test_multimedia_integration():
    """Test multimedia integration - NEW endpoint"""
    try:
        from app.services.chatwoot_service import ChatwootService
        
        # Test that multimedia methods are available in ChatwootService
        chatwoot_service = ChatwootService()
        
        # Check if multimedia methods exist
        has_transcribe = hasattr(chatwoot_service, 'transcribe_audio_from_url')
        has_analyze = hasattr(chatwoot_service, 'analyze_image_from_url')
        has_process_attachment = hasattr(chatwoot_service, 'process_attachment')
        
        return create_success_response({
            "multimedia_integration": {
                "transcribe_audio_from_url": has_transcribe,
                "analyze_image_from_url": has_analyze,
                "process_attachment": has_process_attachment,
                "fully_integrated": has_transcribe and has_analyze and has_process_attachment
            },
            "openai_service_available": chatwoot_service.openai_service is not None,
            "voice_enabled": current_app.config.get('VOICE_ENABLED', False),
            "image_enabled": current_app.config.get('IMAGE_ENABLED', False)
        })
        
    except Exception as e:
        return create_error_response(f"Failed to test multimedia integration: {e}", 500)

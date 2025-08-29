from flask import Blueprint, request, jsonify
from app.services.chatwoot_service import ChatwootService
from app.services.multiagent_system import MultiAgentSystem
from app.models.conversation import ConversationManager
from app.utils.validators import validate_webhook_data
from app.utils.decorators import handle_errors
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('webhook', __name__)

class WebhookError(Exception):
    """Custom exception for webhook errors"""
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

@bp.route('/chatwoot', methods=['POST'])
@handle_errors
def chatwoot_webhook():
    """Handle Chatwoot webhook events"""
    try:
        data = request.get_json()
        event_type = validate_webhook_data(data)
        
        logger.info(f"🔔 WEBHOOK RECEIVED - Event: {event_type}")
        
        chatwoot_service = ChatwootService()
        conversation_manager = ConversationManager()
        multiagent = MultiAgentSystem()
        
        # Handle conversation updates
        if event_type == "conversation_updated":
            success = chatwoot_service.handle_conversation_updated(data)
            status_code = 200 if success else 400
            return jsonify({"status": "conversation_updated_processed", "success": success}), status_code
        
        # Handle only message_created events
        if event_type != "message_created":
            logger.info(f"⏭️ Ignoring event type: {event_type}")
            return jsonify({"status": "ignored_event_type", "event": event_type}), 200
        
        # AGREGADO: Debug completo para imágenes (EXACTLY like monolith)
        if data.get('attachments'):
            chatwoot_service.debug_webhook_data(data)
        
        # Process incoming message
        result = chatwoot_service.process_incoming_message(data, conversation_manager, multiagent)
        
        if result.get("ignored"):
            return jsonify(result), 200
        
        return jsonify(result), 200
        
    except WebhookError as we:
        logger.error(f"Webhook error: {we.message} (Status: {we.status_code})")
        return jsonify({"status": "error", "message": "Error interno del servidor"}), we.status_code
    except Exception as e:
        logger.exception("Error no manejado en webhook")
        return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

@bp.route('/test', methods=['POST'])
@handle_errors  
def test_webhook():
    """Test webhook endpoint for debugging"""
    try:
        data = request.get_json()
        
        chatwoot_service = ChatwootService()
        chatwoot_service.debug_webhook_data(data)
        
        return jsonify({
            "status": "success",
            "message": "Webhook test completed",
            "received_data": data
        }), 200
        
    except Exception as e:
        logger.error(f"Test webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

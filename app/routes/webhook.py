from flask import Blueprint, request, jsonify
from app.services.chatwoot_service import ChatwootService
from app.services.multiagent_system import MultiAgentSystem
from app.models.conversation import ConversationManager
from app.utils.validators import validate_webhook_data
from app.utils.decorators import handle_errors
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('webhook', __name__)

@bp.route('/chatwoot', methods=['POST'])
@handle_errors
def chatwoot_webhook():
    """Handle Chatwoot webhook events"""
    data = request.get_json()
    event_type = validate_webhook_data(data)
    
    logger.info(f"🔔 WEBHOOK RECEIVED - Event: {event_type}")
    
    chatwoot_service = ChatwootService()
    conversation_manager = ConversationManager()
    multiagent = MultiAgentSystem()
    
    # Handle conversation updates
    if event_type == "conversation_updated":
        success = chatwoot_service.handle_conversation_updated(data)
        return jsonify({"status": "conversation_updated_processed", "success": success}), 200
    
    # Handle only message_created events
    if event_type != "message_created":
        logger.info(f"⏭️ Ignoring event type: {event_type}")
        return jsonify({"status": "ignored_event_type", "event": event_type}), 200
    
    # Process incoming message
    result = chatwoot_service.process_incoming_message(data, conversation_manager, multiagent)
    
    return jsonify(result), 200

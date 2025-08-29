from flask import Blueprint, request, jsonify
from app.models.conversation import ConversationManager
from app.utils.decorators import handle_errors
from app.utils.helpers import create_success_response, create_error_response
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('conversations', __name__)

@bp.route('', methods=['GET'])
@handle_errors
def list_conversations():
    """List all conversations with pagination"""
    try:
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 50)), 100)
        
        manager = ConversationManager()
        conversations = manager.list_conversations(page, page_size)
        
        return create_success_response(conversations)
        
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        return create_error_response("Failed to list conversations", 500)

@bp.route('/<user_id>', methods=['GET'])
@handle_errors
def get_conversation(user_id):
    """Get a specific conversation history"""
    try:
        manager = ConversationManager()
        history = manager.get_conversation_details(user_id)
        
        return create_success_response(history)
        
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        return create_error_response("Failed to get conversation", 500)

@bp.route('/<user_id>', methods=['DELETE'])
@handle_errors
def delete_conversation(user_id):
    """Delete a conversation"""
    try:
        manager = ConversationManager()
        success = manager.clear_conversation(user_id)
        
        if success:
            logger.info(f"✅ Conversation {user_id} deleted")
            return create_success_response({
                "message": f"Conversation {user_id} deleted"
            })
        else:
            return create_error_response("Failed to delete conversation", 500)
        
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        return create_error_response("Failed to delete conversation", 500)

@bp.route('/<user_id>/test', methods=['POST'])
@handle_errors
def test_conversation(user_id):
    """Test conversation with a specific user"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return create_error_response("Message is required", 400)
        
        message = data['message'].strip()
        if not message:
            return create_error_response("Message cannot be empty", 400)
        
        from app.services.multiagent_system import MultiAgentSystem
        manager = ConversationManager()
        multiagent = MultiAgentSystem()
        
        response, agent_used = multiagent.get_response(message, user_id, manager)
        
        return create_success_response({
            "user_id": user_id,
            "user_message": message,
            "bot_response": response,
            "agent_used": agent_used,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"Error testing conversation: {e}")
        return create_error_response("Failed to test conversation", 500)

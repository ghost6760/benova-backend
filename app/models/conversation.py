from app.services.redis_service import get_redis_client
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
import logging
import json
import time

logger = logging.getLogger(__name__)

class ConversationManager:
    """Gestión modularizada de conversaciones"""
    
    def __init__(self, max_messages: int = 10):
        self.redis_client = get_redis_client()
        self.max_messages = max_messages
        self.redis_prefix = "conversation:"
        self.message_histories = {}
    
    def _create_user_id(self, contact_id: str) -> str:
        """Generate standardized user ID"""
        if not contact_id.startswith("chatwoot_contact_"):
            return f"chatwoot_contact_{contact_id}"
        return contact_id
    
    def get_chat_history(self, user_id: str, format_type: str = "dict"):
        """Get chat history in specified format"""
        if not user_id:
            return [] if format_type == "dict" else None
        
        try:
            redis_history = self._get_or_create_redis_history(user_id)
            
            if format_type == "langchain":
                return redis_history
            elif format_type == "messages":
                return redis_history.messages
            elif format_type == "dict":
                messages = redis_history.messages
                return [
                    {
                        "role": "user" if isinstance(msg, HumanMessage) else "assistant",
                        "content": msg.content
                    }
                    for msg in messages
                ]
            
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return [] if format_type == "dict" else None
    
    def add_message(self, user_id: str, role: str, content: str) -> bool:
        """Add message to history"""
        if not user_id or not content.strip():
            return False
        
        try:
            history = self._get_or_create_redis_history(user_id)
            
            if role == "user":
                history.add_user_message(content)
            elif role == "assistant":
                history.add_ai_message(content)
            
            self._apply_message_window(user_id)
            return True
            
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return False
    
    def _get_or_create_redis_history(self, user_id: str):
        """Get or create Redis chat history"""
        if user_id not in self.message_histories:
            from flask import current_app
            redis_url = current_app.config['REDIS_URL']
            
            self.message_histories[user_id] = RedisChatMessageHistory(
                session_id=user_id,
                url=redis_url,
                key_prefix="chat_history:",
                ttl=604800  # 7 días
            )
        
        return self.message_histories[user_id]
    
    def _apply_message_window(self, user_id: str):
        """Apply sliding window to messages"""
        try:
            history = self.message_histories.get(user_id)
            if not history:
                return
            
            messages = history.messages
            if len(messages) > self.max_messages:
                messages_to_keep = messages[-self.max_messages:]
                history.clear()
                for message in messages_to_keep:
                    history.add_message(message)
                    
        except Exception as e:
            logger.error(f"Error applying message window: {e}")

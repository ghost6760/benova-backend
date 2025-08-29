from app.services.redis_service import get_redis_client
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
import logging
import json
import time
from typing import Dict, List, Any, Optional

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
    
    def list_conversations(self, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """List all conversations with pagination"""
        try:
            # Get all conversation keys
            pattern = f"{self.redis_prefix}*"
            all_keys = self.redis_client.keys(pattern)
            
            # Extract user IDs
            user_ids = []
            for key in all_keys:
                if key.startswith(self.redis_prefix):
                    user_id = key[len(self.redis_prefix):]
                    user_ids.append(user_id)
            
            # Pagination
            total_conversations = len(user_ids)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_user_ids = user_ids[start_idx:end_idx]
            
            conversations = []
            for user_id in paginated_user_ids:
                try:
                    # Get conversation details
                    details = self.get_conversation_details(user_id)
                    if details:
                        conversations.append(details)
                except Exception as e:
                    logger.warning(f"Error getting details for conversation {user_id}: {e}")
                    continue
            
            return {
                "total_conversations": total_conversations,
                "page": page,
                "page_size": page_size,
                "conversations": conversations
            }
            
        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            return {
                "total_conversations": 0,
                "page": page,
                "page_size": page_size,
                "conversations": []
            }
    
    def get_conversation_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a conversation"""
        try:
            if not user_id:
                return None
            
            # Get chat history
            messages = self.get_chat_history(user_id, format_type="dict")
            
            if not messages:
                return None
            
            # Calculate stats
            user_messages = [msg for msg in messages if msg["role"] == "user"]
            assistant_messages = [msg for msg in messages if msg["role"] == "assistant"]
            
            # Get last activity timestamp (approximation)
            last_updated = None
            try:
                # Try to get from Redis timestamp if available
                history_key = f"chat_history:{user_id}"
                if self.redis_client.exists(history_key):
                    # This is an approximation - Redis doesn't store exact timestamps
                    last_updated = time.time()
            except:
                pass
            
            return {
                "user_id": user_id,
                "message_count": len(messages),
                "user_message_count": len(user_messages),
                "assistant_message_count": len(assistant_messages),
                "messages": messages[-10:],  # Last 10 messages for preview
                "last_updated": last_updated,
                "created_at": None  # Would need to be tracked separately if needed
            }
            
        except Exception as e:
            logger.error(f"Error getting conversation details for {user_id}: {e}")
            return None
    
    def clear_conversation(self, user_id: str) -> bool:
        """Clear/delete a conversation"""
        try:
            if not user_id:
                return False
            
            # Clear from message histories cache
            if user_id in self.message_histories:
                history = self.message_histories[user_id]
                history.clear()
                del self.message_histories[user_id]
            
            # Clear from Redis directly
            history_key = f"chat_history:{user_id}"
            conversation_key = f"{self.redis_prefix}{user_id}"
            
            keys_to_delete = []
            
            # Check if keys exist and add to deletion list
            if self.redis_client.exists(history_key):
                keys_to_delete.append(history_key)
            
            if self.redis_client.exists(conversation_key):
                keys_to_delete.append(conversation_key)
            
            # Delete all related keys
            if keys_to_delete:
                self.redis_client.delete(*keys_to_delete)
            
            logger.info(f"Cleared conversation for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing conversation for {user_id}: {e}")
            return False
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get overall conversation statistics"""
        try:
            # Get all conversation keys
            pattern = f"{self.redis_prefix}*"
            all_keys = self.redis_client.keys(pattern)
            
            total_conversations = len(all_keys)
            
            # Count messages across all conversations
            total_messages = 0
            active_conversations = 0
            
            for key in all_keys[:100]:  # Limit to first 100 to avoid performance issues
                try:
                    if key.startswith(self.redis_prefix):
                        user_id = key[len(self.redis_prefix):]
                        messages = self.get_chat_history(user_id, format_type="dict")
                        if messages:
                            total_messages += len(messages)
                            active_conversations += 1
                except:
                    continue
            
            return {
                "total_conversations": total_conversations,
                "active_conversations": active_conversations,
                "total_messages": total_messages,
                "average_messages_per_conversation": round(total_messages / max(active_conversations, 1), 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting conversation stats: {e}")
            return {
                "total_conversations": 0,
                "active_conversations": 0,
                "total_messages": 0,
                "average_messages_per_conversation": 0
            }

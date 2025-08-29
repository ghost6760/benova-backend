from typing import Dict, Any, Tuple
import json
import logging

logger = logging.getLogger(__name__)

def validate_webhook_data(data: Dict[str, Any]) -> str:
    """Validate webhook data and return event type"""
    if not data:
        raise ValueError("No JSON data received")
    
    event_type = data.get("event")
    if not event_type:
        raise ValueError("Missing event type")
    
    return event_type

def validate_document_data(data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Validate document data"""
    if not data or 'content' not in data:
        raise ValueError("Content is required")
    
    content = data['content'].strip()
    if not content:
        raise ValueError("Content cannot be empty")
    
    # Parse metadata if string
    metadata = data.get('metadata', {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON metadata")
    
    return content, metadata

def validate_conversation_id(conversation_id: Any) -> int:
    """Validate and convert conversation ID"""
    if not conversation_id:
        raise ValueError("Conversation ID is required")
    
    try:
        conv_id = int(conversation_id)
        if conv_id <= 0:
            raise ValueError("Conversation ID must be positive")
        return conv_id
    except (ValueError, TypeError):
        raise ValueError("Invalid conversation ID format")

def validate_user_id(user_id: Any) -> str:
    """Validate user ID"""
    if not user_id or not str(user_id).strip():
        raise ValueError("User ID is required")
    
    return str(user_id).strip()

def validate_message_content(content: Any) -> str:
    """Validate message content"""
    if not content:
        return ""
    
    content_str = str(content).strip()
    return content_str

def validate_search_query(query: Any, max_k: int = 20) -> Tuple[str, int]:
    """Validate search query and k parameter"""
    if not query or not str(query).strip():
        raise ValueError("Query cannot be empty")
    
    query_str = str(query).strip()
    
    # Validate k parameter
    k = 3  # default
    if 'k' in query:
        try:
            k = int(query.get('k', 3))
            k = max(1, min(k, max_k))
        except:
            k = 3
    
    return query_str, k

def validate_pagination(page: Any, page_size: Any, max_page_size: int = 100) -> Tuple[int, int]:
    """Validate pagination parameters"""
    try:
        page_num = max(1, int(page))
    except:
        page_num = 1
    
    try:
        size = max(1, min(int(page_size), max_page_size))
    except:
        size = 50
    
    return page_num, size

from flask import jsonify
from typing import Dict, Any
import hashlib
import time
from datetime import datetime

def create_success_response(data: Dict[str, Any], status_code: int = 200):
    """Create standardized success response"""
    return jsonify({"status": "success", **data}), status_code

def create_error_response(message: str, status_code: int = 400):
    """Create standardized error response"""
    return jsonify({"status": "error", "message": message}), status_code

def generate_doc_id(content: str) -> str:
    """Generate document ID from content"""
    return hashlib.md5(content.encode()).hexdigest()

def get_timestamp() -> float:
    """Get current timestamp"""
    return time.time()

def get_iso_timestamp() -> str:
    """Get current ISO timestamp"""
    return datetime.utcnow().isoformat()

def sanitize_user_id(user_id: str) -> str:
    """Sanitize and format user ID"""
    if not user_id.startswith("chatwoot_contact_"):
        return f"chatwoot_contact_{user_id}"
    return user_id

def extract_file_extension(url: str, content_type: str = "") -> str:
    """Extract file extension from URL or content type"""
    # Check content type first
    content_type_lower = content_type.lower()
    
    if 'mp3' in content_type_lower or url.endswith('.mp3'):
        return '.mp3'
    elif 'wav' in content_type_lower or url.endswith('.wav'):
        return '.wav'
    elif 'm4a' in content_type_lower or url.endswith('.m4a'):
        return '.m4a'
    elif 'ogg' in content_type_lower or url.endswith('.ogg'):
        return '.ogg'
    elif 'jpeg' in content_type_lower or 'jpg' in content_type_lower:
        return '.jpg'
    elif 'png' in content_type_lower or url.endswith('.png'):
        return '.png'
    elif 'gif' in content_type_lower or url.endswith('.gif'):
        return '.gif'
    elif 'webp' in content_type_lower or url.endswith('.webp'):
        return '.webp'
    
    # Default based on content type category
    if 'audio' in content_type_lower:
        return '.mp3'
    elif 'image' in content_type_lower:
        return '.jpg'
    
    return ''

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def safe_json_parse(json_str: str, default: Any = None) -> Any:
    """Safely parse JSON with default value"""
    try:
        import json
        return json.loads(json_str)
    except:
        return default

def calculate_chunks_needed(text_length: int, chunk_size: int = 1000, overlap: int = 200) -> int:
    """Calculate approximate number of chunks needed"""
    if text_length <= chunk_size:
        return 1
    
    effective_chunk_size = chunk_size - overlap
    return ((text_length - chunk_size) // effective_chunk_size) + 1

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from datetime import datetime

class DocumentInput(BaseModel):
    """Schema for document input"""
    content: str = Field(..., min_length=1, description="Document content")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Document metadata")
    
    @validator('content')
    def content_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Content cannot be empty or whitespace only')
        return v

class BulkDocumentInput(BaseModel):
    """Schema for bulk document input"""
    documents: List[DocumentInput] = Field(..., min_items=1, description="List of documents")

class MessageInput(BaseModel):
    """Schema for message input"""
    message: str = Field(..., min_length=1, description="Message content")
    user_id: Optional[str] = Field(None, description="User ID")
    
class WebhookData(BaseModel):
    """Schema for webhook data validation"""
    event: str = Field(..., description="Event type")
    id: Optional[int] = Field(None, description="Message ID")
    content: Optional[str] = Field("", description="Message content")
    message_type: Optional[str] = Field(None, description="Message type")
    conversation: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Conversation data")
    attachments: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Message attachments")
    sender: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Sender information")

class SearchQuery(BaseModel):
    """Schema for search queries"""
    query: str = Field(..., min_length=1, description="Search query")
    k: int = Field(3, ge=1, le=20, description="Number of results")
    
class ConversationResponse(BaseModel):
    """Schema for conversation responses"""
    user_id: str
    message_count: int
    messages: List[Dict[str, str]]
    last_updated: Optional[str]

class HealthResponse(BaseModel):
    """Schema for health check responses"""
    status: str = Field(..., pattern="^(healthy|unhealthy|error)$")
    timestamp: float
    components: Dict[str, Any]
    configuration: Optional[Dict[str, Any]]
    error: Optional[str]

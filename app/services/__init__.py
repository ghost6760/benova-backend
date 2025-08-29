"""Services package initialization - UPDATED with all services"""

from .chatwoot_service import ChatwootService
from .openai_service import OpenAIService, init_openai
from .redis_service import get_redis_client, init_redis, close_redis
from .vectorstore_service import VectorstoreService, init_vectorstore
from .multiagent_system import MultiAgentSystem
from .multimedia_service import MultimediaService  # NOW IMPORTED

__all__ = [
    'ChatwootService',
    'OpenAIService',
    'init_openai',
    'get_redis_client',
    'init_redis', 
    'close_redis',
    'VectorstoreService',
    'init_vectorstore',
    'MultiAgentSystem',
    'MultimediaService'  # NOW EXPORTED
]

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuración base"""
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = False
    TESTING = False
    
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-4o-mini')
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
    MAX_TOKENS = int(os.getenv('MAX_TOKENS', 1500))
    TEMPERATURE = float(os.getenv('TEMPERATURE', 0.7))
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    # Chatwoot
    CHATWOOT_API_KEY = os.getenv('CHATWOOT_API_KEY')
    CHATWOOT_BASE_URL = os.getenv('CHATWOOT_BASE_URL', 'https://chatwoot-production-0f1d.up.railway.app')
    ACCOUNT_ID = os.getenv('ACCOUNT_ID', '7')
    
    # App settings
    PORT = int(os.getenv('PORT', 8080))
    MAX_CONTEXT_MESSAGES = int(os.getenv('MAX_CONTEXT_MESSAGES', 10))
    SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', 0.7))
    MAX_RETRIEVED_DOCS = int(os.getenv('MAX_RETRIEVED_DOCS', 3))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Features
    VOICE_ENABLED = os.getenv('VOICE_ENABLED', 'false').lower() == 'true'
    IMAGE_ENABLED = os.getenv('IMAGE_ENABLED', 'false').lower() == 'true'
    
    # Schedule Service
    SCHEDULE_SERVICE_URL = os.getenv('SCHEDULE_SERVICE_URL', 'http://127.0.0.1:4040')
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')

    API_KEY = os.getenv('API_KEY')  # Para endpoints de admin

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = True
    REDIS_URL = 'redis://localhost:6379/1'  # Different DB for testing

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}

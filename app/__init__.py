from flask import Flask
from app.config import Config
from app.utils.error_handlers import register_error_handlers
from app.services.redis_service import init_redis
from app.services.vectorstore_service import init_vectorstore
from app.services.openai_service import init_openai  # This import was missing
import logging
import sys

def create_app(config_class=Config):
    """Factory pattern para crear la aplicación Flask"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Configurar logging
    logging.basicConfig(
        level=app.config.get('LOG_LEVEL', 'INFO'),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # Inicializar servicios
    with app.app_context():
        init_redis(app)
        init_openai(app)
        init_vectorstore(app)
    
    # Registrar blueprints
    from app.routes import webhook, documents, conversations, health, multimedia, admin
    
    app.register_blueprint(webhook.bp, url_prefix='/webhook')
    app.register_blueprint(documents.bp, url_prefix='/documents')
    app.register_blueprint(conversations.bp, url_prefix='/conversations')
    app.register_blueprint(health.bp, url_prefix='/health')
    app.register_blueprint(multimedia.bp, url_prefix='/media')
    app.register_blueprint(admin.bp, url_prefix='/admin')
    
    # Registrar error handlers
    register_error_handlers(app)
    
    # Root route
    @app.route('/')
    def index():
        return {"status": "healthy", "message": "Benova Backend API is running"}
    
    return app


def initialize_protection_system():
    """Inicializar protección después de crear la app"""
    try:
        # Debe ejecutarse después de que modern_rag_system esté disponible
        from app.services.vectorstore_service import apply_vectorstore_protection
        apply_vectorstore_protection()
        logger.info("✅ Vectorstore protection applied")
    except Exception as e:
        logger.warning(f"Could not apply vectorstore protection: {e}")

def startup_checks():
    """Verificaciones completas de inicio"""
    try:
        # Validar Redis
        redis_client.ping()
        
        # Validar OpenAI
        openai_service = OpenAIService()
        if not openai_service.validate_openai_setup():
            raise Exception("OpenAI validation failed")
        
        # Validar Vectorstore
        vectorstore_service = VectorstoreService()
        vectorstore_service.test_connection()
        
        logger.info("All startup checks passed")
        return True
    except Exception as e:
        logger.error(f"Startup check failed: {e}")
        raise

@app.before_request
def ensure_vectorstore_health():
    """Middleware que verifica salud del vectorstore"""
    vector_endpoints = ['/webhook/chatwoot', '/documents', '/chat']
    
    if any(endpoint in request.path for endpoint in vector_endpoints):
        try:
            # Verificación no-bloqueante del estado del índice
            pass  # Implementar según tu lógica de recuperación
        except Exception as e:
            logger.error(f"Error in health check middleware: {e}")

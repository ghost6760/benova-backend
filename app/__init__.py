from flask import Flask
from app.config import Config
from app.utils.error_handlers import register_error_handlers
from app.services.redis_service import init_redis
from app.services.vectorstore_service import init_vectorstore
from app.services.openai_service import init_openai
import logging
import sys

def create_app(config_class=Config):
    """Factory pattern para crear la aplicación Flask"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Configurar logging
    logging.basicConfig(
        level=app.config['LOG_LEVEL'],
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
    
    # Rutas estáticas
    @app.route('/')
    def index():
        return app.send_static_file('index.html')
    
    return app

from flask import Flask, request, send_from_directory
from app.config import Config
from app.utils.error_handlers import register_error_handlers
from app.services.redis_service import init_redis
from app.services.vectorstore_service import init_vectorstore
from app.services.openai_service import init_openai
from app.routes import webhook, documents, conversations, health, multimedia, admin
import logging
import sys
import threading
import time

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
    
    logger = logging.getLogger(__name__)
    
    # Inicializar servicios
    with app.app_context():
        init_redis(app)
        init_openai(app)
        init_vectorstore(app)
    
    # ENHANCED: Middleware de protección vectorstore
    @app.before_request
    def ensure_vectorstore_health():
        """Middleware que verifica salud del vectorstore"""
        vector_endpoints = ['/webhook/chatwoot', '/documents', '/chat']
        
        if any(endpoint in request.path for endpoint in vector_endpoints):
            try:
                # Solo aplicar recovery si está habilitado
                if app.config.get('VECTORSTORE_AUTO_RECOVERY', True):
                    from app.services.vector_auto_recovery import get_auto_recovery_instance
                    auto_recovery = get_auto_recovery_instance()
                    
                    if auto_recovery:
                        # Verificación no-bloqueante del estado del índice
                        health = auto_recovery.verify_index_health()
                        
                        if not health["healthy"] and health["stored_documents"] > 0:
                            # Recovery en background para no bloquear request
                            def background_recovery():
                                try:
                                    auto_recovery.ensure_index_healthy()
                                except:
                                    pass
                            
                            threading.Thread(target=background_recovery, daemon=True).start()
                            
            except Exception as e:
                logger.error(f"Error in health check middleware: {e}")
                # NUNCA bloquear requests
    
    # Registrar blueprints
    app.register_blueprint(webhook.bp, url_prefix='/webhook')
    app.register_blueprint(documents.bp, url_prefix='/documents')
    app.register_blueprint(conversations.bp, url_prefix='/conversations')
    app.register_blueprint(health.bp, url_prefix='/health')
    app.register_blueprint(multimedia.bp, url_prefix='/multimedia')
    app.register_blueprint(admin.bp, url_prefix='/admin')
    
    # Registrar error handlers
    register_error_handlers(app)
    
    # Root route
    @app.route('/')
    def index():
        return {"status": "healthy", "message": "Benova Backend API is running"}

    @app.route('/')
    def serve_frontend():
        return send_from_directory('.', 'index.html')
    
    @app.route('/<path:filename>')
    def serve_static(filename):
        return send_from_directory('.', filename)
    
    # ENHANCED: Inicializar sistemas de protección después de crear la app
    with app.app_context():
        initialize_protection_system(app)
    
    return app

def initialize_protection_system(app):
    """Inicializar sistema de protección después de crear la app"""
    try:
        from app.services.vector_auto_recovery import (
            initialize_auto_recovery_system, 
            apply_vectorstore_protection
        )
        from app.services.vectorstore_service import VectorstoreService
        
        # Inicializar auto-recovery
        if initialize_auto_recovery_system():
            app.logger.info("Auto-recovery system initialized")
            
            # Aplicar protección a vectorstore service
            try:
                vectorstore_service = VectorstoreService()
                if apply_vectorstore_protection(vectorstore_service):
                    app.logger.info("Vectorstore protection applied")
                else:
                    app.logger.warning("Could not apply vectorstore protection")
            except Exception as e:
                app.logger.warning(f"Vectorstore protection failed: {e}")
        else:
            app.logger.warning("Could not initialize auto-recovery system")
            
    except Exception as e:
        app.logger.warning(f"Could not initialize protection system: {e}")

def startup_checks(app):
    """Verificaciones completas de inicio"""
    try:
        with app.app_context():
            from app.services.redis_service import get_redis_client
            from app.services.openai_service import OpenAIService
            from app.services.vectorstore_service import VectorstoreService
            
            # Validar Redis
            redis_client = get_redis_client()
            redis_client.ping()
            
            # Validar OpenAI
            openai_service = OpenAIService()
            openai_service.test_connection()
            
            # Validar Vectorstore
            vectorstore_service = VectorstoreService()
            vectorstore_service.test_connection()
            
            app.logger.info("All startup checks passed")
            return True
    except Exception as e:
        app.logger.error(f"Startup check failed: {e}")
        raise

def delayed_initialization(app):
    """
    Inicialización inteligente que espera a que todo esté listo
    SE EJECUTA EN BACKGROUND después de que Flask esté completamente cargado
    """
    max_attempts = 10
    attempt = 0
    
    with app.app_context():
        while attempt < max_attempts:
            try:
                attempt += 1
                
                from app.services.vector_auto_recovery import get_auto_recovery_instance
                auto_recovery = get_auto_recovery_instance()
                
                if auto_recovery:
                    app.logger.info(f"Auto-recovery system found on attempt {attempt}")
                    
                    # Verificar salud inicial
                    health = auto_recovery.verify_index_health()
                    if health.get("needs_recovery", False):
                        app.logger.info("Performing initial index recovery...")
                        auto_recovery.ensure_index_healthy()
                    
                    app.logger.info("Auto-recovery system fully operational")
                    break
                else:
                    app.logger.info(f"Waiting for auto-recovery system... attempt {attempt}")
                
                time.sleep(2)  # Esperar 2 segundos entre intentos
                
            except Exception as e:
                app.logger.error(f"Error in delayed initialization attempt {attempt}: {e}")
                time.sleep(2)
        
        if attempt >= max_attempts:
            app.logger.error("Failed to initialize auto-recovery after maximum attempts")

def start_background_initialization(app):
    """Iniciar proceso de inicialización en background"""
    try:
        init_thread = threading.Thread(
            target=delayed_initialization, 
            args=(app,),
            daemon=True
        )
        init_thread.start()
        app.logger.info("Background initialization started")
    except Exception as e:
        app.logger.error(f"Error starting background initialization: {e}")

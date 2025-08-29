from app.services.redis_service import get_redis_client
from app.services.vectorstore_service import VectorstoreService
from flask import current_app
import logging
import json
import time
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class RedisVectorAutoRecovery:
    """
    Sistema de auto-recuperación para vectorstore Redis - COMPLETE implementation like monolith
    """
    
    def __init__(self, index_name="benova_documents"):
        self.redis_client = get_redis_client()
        self.index_name = index_name
        self.metadata_key = f"__recovery_metadata__{index_name}"
        self.backup_key = f"__backup_docs__{index_name}"
        self.documents_pattern = f"{index_name}:*"
        self.health_cache = {"last_check": 0, "status": None}
        self._recovery_lock = threading.Lock()
        
        # Configuration from app config
        self.health_check_interval = current_app.config.get('VECTORSTORE_HEALTH_CHECK_INTERVAL', 30)
        self.recovery_timeout = current_app.config.get('VECTORSTORE_RECOVERY_TIMEOUT', 60)
        self.auto_recovery_enabled = current_app.config.get('VECTORSTORE_AUTO_RECOVERY', True)
        
    def verify_index_health(self) -> Dict[str, Any]:
        """Verificar estado del índice con cache inteligente"""
        current_time = time.time()
        
        # Cache for health_check_interval seconds
        if (current_time - self.health_cache["last_check"]) < self.health_check_interval and self.health_cache["status"]:
            return self.health_cache["status"]
        
        try:
            # Verificar índice
            info = self.redis_client.ft(self.index_name).info()
            doc_count = info.get('num_docs', 0)
            
            # Contar documentos almacenados
            stored_keys = list(self.redis_client.scan_iter(match=self.documents_pattern))
            stored_count = len(stored_keys)
            
            health_status = {
                "index_exists": True,
                "index_functional": doc_count > 0,
                "stored_documents": stored_count,
                "index_doc_count": doc_count,
                "needs_recovery": doc_count == 0 and stored_count > 0,
                "healthy": doc_count > 0 and stored_count > 0,
                "timestamp": current_time
            }
            
            self.health_cache = {"last_check": current_time, "status": health_status}
            return health_status
            
        except Exception as e:
            logger.error(f"Error checking index health: {e}")
            health_status = {
                "index_exists": False,
                "index_functional": False,
                "stored_documents": 0,
                "needs_recovery": True,
                "healthy": False,
                "error": str(e),
                "timestamp": current_time
            }
            self.health_cache = {"last_check": current_time, "status": health_status}
            return health_status
    
    def reconstruct_index_from_stored_data(self) -> bool:
        """Reconstruir índice desde datos almacenados"""
        if not self.auto_recovery_enabled:
            logger.warning("Auto-recovery is disabled")
            return False
            
        with self._recovery_lock:
            try:
                logger.info("Starting index reconstruction...")
                
                # Obtener documentos almacenados
                stored_docs = self._get_stored_documents()
                if not stored_docs:
                    logger.warning("No stored documents found")
                    return False
                
                # Eliminar índice corrupto
                try:
                    self.redis_client.ft(self.index_name).dropindex(delete_documents=False)
                    logger.info("Dropped corrupted index")
                except:
                    pass
                
                time.sleep(1)
                
                # Recrear índice usando VectorstoreService
                try:
                    vectorstore_service = VectorstoreService()
                    vectorstore_service._initialize_vectorstore()
                    
                    # Limpiar cache
                    self.health_cache = {"last_check": 0, "status": None}
                    
                    logger.info(f"Index reconstructed: {len(stored_docs)} docs available")
                    return True
                    
                except Exception as e:
                    logger.error(f"Error recreating index: {e}")
                    return False
                
            except Exception as e:
                logger.error(f"Error in reconstruction: {e}")
                return False
    
    def _get_stored_documents(self) -> List[Dict]:
        """Obtener documentos almacenados"""
        try:
            docs = []
            keys = list(self.redis_client.scan_iter(match=self.documents_pattern))
            
            for key in keys:
                try:
                    doc_data = self.redis_client.hgetall(key)
                    if doc_data:
                        doc = {}
                        for k, v in doc_data.items():
                            key_str = k.decode() if isinstance(k, bytes) else k
                            val_str = v.decode() if isinstance(v, bytes) else v
                            doc[key_str] = val_str
                        docs.append(doc)
                except Exception as e:
                    logger.warning(f"Error processing document {key}: {e}")
                    continue
            
            return docs
            
        except Exception as e:
            logger.error(f"Error getting stored documents: {e}")
            return []
    
    def ensure_index_healthy(self) -> bool:
        """Método principal de recuperación"""
        try:
            health = self.verify_index_health()
            
            if health["needs_recovery"] and self.auto_recovery_enabled:
                logger.warning("Index needs recovery, attempting reconstruction...")
                return self.reconstruct_index_from_stored_data()
            
            return health["healthy"]
            
        except Exception as e:
            logger.error(f"Error ensuring index health: {e}")
            return False
    
    def get_protection_status(self) -> Dict[str, Any]:
        """Get protection status"""
        health = self.verify_index_health()
        
        return {
            "vectorstore_healthy": health.get("healthy", False),
            "index_exists": health.get("index_exists", False),
            "needs_recovery": health.get("needs_recovery", False),
            "protection_active": True,
            "auto_recovery_enabled": self.auto_recovery_enabled,
            "auto_recovery_available": True,
            "health_check_interval": self.health_check_interval,
            "last_health_check": self.health_cache.get("last_check", 0)
        }


class VectorstoreProtectionMiddleware:
    """
    Middleware para proteger operaciones del vectorstore - COMPLETE like monolith
    """
    
    def __init__(self, auto_recovery: RedisVectorAutoRecovery):
        self.auto_recovery = auto_recovery
        self._original_methods = {}
        
    def apply_protection(self, vectorstore_service: VectorstoreService) -> bool:
        """Aplicar protección automática a métodos críticos"""
        try:
            # Proteger vectorstore.add_texts
            if hasattr(vectorstore_service.vectorstore, 'add_texts'):
                original_add_texts = vectorstore_service.vectorstore.add_texts
                
                def protected_add_texts(texts, metadatas=None, **kwargs):
                    try:
                        # Verificar salud antes de agregar
                        if self.auto_recovery.auto_recovery_enabled:
                            self.auto_recovery.ensure_index_healthy()
                        
                        result = original_add_texts(texts, metadatas, **kwargs)
                        logger.debug(f"Protected add_texts: {len(texts)} texts")
                        return result
                        
                    except Exception as e:
                        logger.error(f"Protected add_texts failed: {e}")
                        
                        # Recovery y retry
                        if self.auto_recovery.ensure_index_healthy():
                            try:
                                return original_add_texts(texts, metadatas, **kwargs)
                            except Exception as retry_error:
                                logger.error(f"Retry failed: {retry_error}")
                        
                        raise e
                
                vectorstore_service.vectorstore.add_texts = protected_add_texts
                self._original_methods['add_texts'] = original_add_texts
                logger.info("Vectorstore add_texts protected")
            
            # Proteger retriever.invoke
            if hasattr(vectorstore_service, 'get_retriever'):
                retriever = vectorstore_service.get_retriever()
                if hasattr(retriever, 'invoke'):
                    original_invoke = retriever.invoke
                    
                    def protected_retriever_invoke(input_query, config=None, **kwargs):
                        try:
                            # Verificar salud antes de buscar
                            if self.auto_recovery.auto_recovery_enabled:
                                health = self.auto_recovery.verify_index_health()
                                if not health["healthy"] and health["stored_documents"] > 0:
                                    self.auto_recovery.ensure_index_healthy()
                            
                            return original_invoke(input_query, config, **kwargs)
                            
                        except Exception as e:
                            logger.error(f"Protected retriever failed: {e}")
                            
                            # Recovery y retry
                            if self.auto_recovery.reconstruct_index_from_stored_data():
                                try:
                                    return original_invoke(input_query, config, **kwargs)
                                except:
                                    logger.error("Final retry failed")
                            
                            # Retornar vacío para no romper
                            logger.warning("Returning empty results due to failure")
                            return []
                    
                    retriever.invoke = protected_retriever_invoke
                    self._original_methods['retriever_invoke'] = original_invoke
                    logger.info("Retriever invoke protected")
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying protection: {e}")
            return False
    
    def remove_protection(self, vectorstore_service: VectorstoreService) -> bool:
        """Remover protección y restaurar métodos originales"""
        try:
            if 'add_texts' in self._original_methods:
                vectorstore_service.vectorstore.add_texts = self._original_methods['add_texts']
                
            if 'retriever_invoke' in self._original_methods:
                retriever = vectorstore_service.get_retriever()
                retriever.invoke = self._original_methods['retriever_invoke']
                
            self._original_methods.clear()
            logger.info("Vectorstore protection removed")
            return True
            
        except Exception as e:
            logger.error(f"Error removing protection: {e}")
            return False


# Global instances
_auto_recovery_instance: Optional[RedisVectorAutoRecovery] = None
_protection_middleware: Optional[VectorstoreProtectionMiddleware] = None


def initialize_auto_recovery_system() -> bool:
    """Inicializar sistema de auto-recovery global"""
    global _auto_recovery_instance, _protection_middleware
    
    try:
        if _auto_recovery_instance is None:
            _auto_recovery_instance = RedisVectorAutoRecovery()
            logger.info("Redis Auto-Recovery system initialized")
        
        if _protection_middleware is None:
            _protection_middleware = VectorstoreProtectionMiddleware(_auto_recovery_instance)
            logger.info("Protection middleware initialized")
        
        return True
        
    except Exception as e:
        logger.error(f"Error initializing auto-recovery: {e}")
        return False


def apply_vectorstore_protection(vectorstore_service) -> bool:
    """Aplicar protección a un servicio de vectorstore"""
    global _protection_middleware
    
    if _protection_middleware is None:
        logger.error("Protection middleware not initialized")
        return False
    
    return _protection_middleware.apply_protection(vectorstore_service)


def get_auto_recovery_instance() -> Optional[RedisVectorAutoRecovery]:
    """Obtener instancia global de auto-recovery"""
    return _auto_recovery_instance


def get_health_recommendations(health: Dict) -> List[str]:
    """Generar recomendaciones de salud"""
    recommendations = []
    
    if health.get("needs_recovery"):
        recommendations.append("Index needs reconstruction - will auto-repair on next operation")
    
    if not health.get("index_exists"):
        recommendations.append("Index missing - will be recreated from stored documents")
    
    if health.get("healthy"):
        recommendations.append("System is healthy - no action required")
    
    return recommendations

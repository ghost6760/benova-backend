from app.services.redis_service import get_redis_client
from datetime import datetime

import hashlib
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class DocumentManager:
    """Manager for document operations"""
    
    def __init__(self):
        self.redis_client = get_redis_client()
        self.change_tracker = DocumentChangeTracker(self.redis_client)
    
    def add_document(self, content: str, metadata: Dict[str, Any], 
                    vectorstore_service) -> Tuple[str, int]:
        """Add a single document"""
        # Generate doc_id
        doc_id = hashlib.md5(content.encode()).hexdigest()
        metadata['doc_id'] = doc_id
        
        # Create chunks
        texts, chunk_metadatas = vectorstore_service.create_chunks(content)
        
        # Add doc_id to all chunk metadata
        for i, chunk_meta in enumerate(chunk_metadatas):
            chunk_meta.update(metadata)
            chunk_meta['chunk_index'] = i
        
        # Add to vectorstore
        vectorstore_service.add_texts(texts, chunk_metadatas)
        
        # Save document in Redis
        doc_key = f"document:{doc_id}"
        doc_data = {
            'content': content,
            'metadata': json.dumps(metadata),
            'created_at': datetime.utcnow().isoformat(),
            'chunk_count': str(len(texts))
        }
        
        self.redis_client.hset(doc_key, mapping=doc_data)
        
        # Track change
        self.change_tracker.register_document_change(doc_id, 'added')
        
        return doc_id, len(texts)
    
    def bulk_add_documents(self, documents: List[Dict[str, Any]], 
                          vectorstore_service) -> Dict[str, Any]:
        """Bulk add multiple documents"""
        added_docs = 0
        total_chunks = 0
        errors = []
        added_doc_ids = []
        
        for i, doc_data in enumerate(documents):
            try:
                content = doc_data.get('content', '').strip()
                metadata = doc_data.get('metadata', {})
                
                if not content:
                    raise ValueError("Content cannot be empty")
                
                doc_id, num_chunks = self.add_document(content, metadata, vectorstore_service)
                
                added_docs += 1
                total_chunks += num_chunks
                added_doc_ids.append(doc_id)
                
            except Exception as e:
                errors.append(f"Document {i}: {str(e)}")
                continue
        
        response_data = {
            "documents_added": added_docs,
            "total_chunks": total_chunks,
            "message": f"Added {added_docs} documents with {total_chunks} chunks"
        }
        
        if errors:
            response_data["errors"] = errors
        
        return response_data
    
    def delete_document(self, doc_id: str, vectorstore_service) -> Dict[str, Any]:
        """Delete a document and its vectors"""
        doc_key = f"document:{doc_id}"
        
        if not self.redis_client.exists(doc_key):
            return {"found": False}
        
        # Find and delete vectors
        vectors = vectorstore_service.find_vectors_by_doc_id(doc_id)
        vectors_deleted = vectorstore_service.delete_vectors(vectors)
        
        # Delete document
        self.redis_client.delete(doc_key)
        
        # Track change
        self.change_tracker.register_document_change(doc_id, 'deleted')
        
        return {
            "found": True,
            "message": "Document deleted successfully",
            "vectors_deleted": vectors_deleted
        }
    
    def list_documents(self, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """List documents with pagination"""
        doc_pattern = "document:*"
        doc_keys = self.redis_client.keys(doc_pattern)
        
        # Pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_keys = doc_keys[start_idx:end_idx]
        
        documents = []
        for key in paginated_keys:
            try:
                doc_data = self.redis_client.hgetall(key)
                if doc_data:
                    doc_id = key.split(':', 1)[1]
                    content = doc_data.get('content', '')
                    metadata = json.loads(doc_data.get('metadata', '{}'))
                    
                    documents.append({
                        "id": doc_id,
                        "content": content[:200] + "..." if len(content) > 200 else content,
                        "metadata": metadata,
                        "created_at": doc_data.get('created_at'),
                        "chunk_count": int(doc_data.get('chunk_count', 0))
                    })
                    
            except Exception as e:
                logger.warning(f"Error parsing document {key}: {e}")
                continue
        
        return {
            "total_documents": len(doc_keys),
            "page": page,
            "page_size": page_size,
            "documents": documents
        }
    
    def cleanup_orphaned_vectors(self, vectorstore_service, dry_run: bool = True) -> Dict[str, Any]:
        """Clean up orphaned vectors"""
        # Get all documents
        doc_keys = self.redis_client.keys("document:*")
        existing_doc_ids = set()
        
        for key in doc_keys:
            doc_id = key.split(':', 1)[1]
            existing_doc_ids.add(doc_id)
        
        # Get all vectors
        vector_pattern = f"{vectorstore_service.index_name}:*"
        vector_keys = self.redis_client.keys(vector_pattern)
        
        orphaned_vectors = []
        
        for vector_key in vector_keys:
            try:
                doc_id = None
                
                # Check direct field
                doc_id_direct = self.redis_client.hget(vector_key, 'doc_id')
                if doc_id_direct:
                    doc_id = doc_id_direct
                else:
                    # Check metadata
                    metadata_str = self.redis_client.hget(vector_key, 'metadata')
                    if metadata_str:
                        metadata = json.loads(metadata_str)
                        doc_id = metadata.get('doc_id')
                
                if doc_id and doc_id not in existing_doc_ids:
                    orphaned_vectors.append({
                        "vector_key": vector_key,
                        "doc_id": doc_id
                    })
                    
            except Exception as e:
                logger.warning(f"Error checking vector {vector_key}: {e}")
                continue
        
        # Delete if not dry run
        deleted_count = 0
        if not dry_run and orphaned_vectors:
            keys_to_delete = [v["vector_key"] for v in orphaned_vectors]
            deleted_count = vectorstore_service.delete_vectors(keys_to_delete)
        
        return {
            "total_vectors": len(vector_keys),
            "total_documents": len(existing_doc_ids),
            "orphaned_vectors_found": len(orphaned_vectors),
            "orphaned_vectors_deleted": deleted_count,
            "dry_run": dry_run,
            "orphaned_samples": orphaned_vectors[:10]
        }
    
    def get_diagnostics(self, vectorstore_service) -> Dict[str, Any]:
        """Get system diagnostics"""
        doc_keys = self.redis_client.keys("document:*")
        vector_keys = self.redis_client.keys(f"{vectorstore_service.index_name}:*")
        
        doc_id_counts = {}
        vectors_without_doc_id = 0
        
        for vector_key in vector_keys:
            try:
                doc_id = None
                
                doc_id_direct = self.redis_client.hget(vector_key, 'doc_id')
                if doc_id_direct:
                    doc_id = doc_id_direct
                else:
                    metadata_str = self.redis_client.hget(vector_key, 'metadata')
                    if metadata_str:
                        metadata = json.loads(metadata_str)
                        doc_id = metadata.get('doc_id')
                
                if doc_id:
                    doc_id_counts[doc_id] = doc_id_counts.get(doc_id, 0) + 1
                else:
                    vectors_without_doc_id += 1
                    
            except Exception as e:
                logger.warning(f"Error analyzing vector: {e}")
                continue
        
        orphaned_docs = []
        for doc_key in doc_keys:
            doc_id = doc_key.split(':', 1)[1]
            if doc_id not in doc_id_counts:
                orphaned_docs.append(doc_id)
        
        return {
            "total_documents": len(doc_keys),
            "total_vectors": len(vector_keys),
            "vectors_without_doc_id": vectors_without_doc_id,
            "documents_with_vectors": len(doc_id_counts),
            "orphaned_documents": len(orphaned_docs),
            "avg_vectors_per_doc": round(sum(doc_id_counts.values()) / len(doc_id_counts), 2) if doc_id_counts else 0,
            "sample_doc_vector_counts": dict(list(doc_id_counts.items())[:10]),
            "orphaned_doc_samples": orphaned_docs[:5]
        }


class DocumentChangeTracker:
   """Track document changes for cache invalidation"""
   
   def __init__(self, redis_client):
       self.redis_client = redis_client
       self.version_key = "vectorstore_version"
       self.doc_hash_key = "document_hashes"
   
   def get_current_version(self) -> int:
       """Get current version of vectorstore"""
       try:
           version = self.redis_client.get(self.version_key)
           return int(version) if version else 0
       except:
           return 0
   
   def increment_version(self):
       """Increment version of vectorstore"""
       try:
           self.redis_client.incr(self.version_key)
           logger.info(f"Vectorstore version incremented to {self.get_current_version()}")
       except Exception as e:
           logger.error(f"Error incrementing version: {e}")
   
   def register_document_change(self, doc_id: str, change_type: str):
       """Register document change"""
       try:
           change_data = {
               'doc_id': doc_id,
               'change_type': change_type,
               'timestamp': datetime.utcnow().isoformat()
           }
           
           change_key = f"doc_change:{doc_id}:{int(time.time())}"
           self.redis_client.setex(change_key, 3600, json.dumps(change_data))
           
           self.increment_version()
           
           logger.info(f"Document change registered: {doc_id} - {change_type}")
           
       except Exception as e:
           logger.error(f"Error registering document change: {e}")

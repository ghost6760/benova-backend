from flask import Blueprint, request, jsonify
from app.services.vectorstore_service import VectorstoreService
from app.models.document import DocumentManager
from app.utils.validators import validate_document_data
from app.utils.decorators import handle_errors, require_api_key
from app.utils.helpers import create_success_response, create_error_response
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('documents', __name__)

@bp.route('', methods=['POST'])
@handle_errors
def add_document():
    """Add a single document to the vectorstore"""
    try:
        data = request.get_json()
        content, metadata = validate_document_data(data)
        
        doc_manager = DocumentManager()
        vectorstore_service = VectorstoreService()
        
        doc_id, num_chunks = doc_manager.add_document(content, metadata, vectorstore_service)
        
        logger.info(f"✅ Document {doc_id} added with {num_chunks} chunks")
        
        return create_success_response({
            "document_id": doc_id,
            "chunk_count": num_chunks,
            "message": f"Document added with {num_chunks} chunks"
        }, 201)
        
    except ValueError as e:
        return create_error_response(str(e), 400)
    except Exception as e:
        logger.exception("Error adding document")
        return create_error_response("Failed to add document", 500)

@bp.route('', methods=['GET'])
@handle_errors
def list_documents():
    """List all documents with pagination"""
    try:
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 50)), 100)
        
        doc_manager = DocumentManager()
        result = doc_manager.list_documents(page, page_size)
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        return create_error_response("Failed to list documents", 500)

@bp.route('/search', methods=['POST'])
@handle_errors
def search_documents():
    """Search documents using semantic search"""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return create_error_response("Query is required", 400)
        
        query = data['query'].strip()
        if not query:
            return create_error_response("Query cannot be empty", 400)
        
        k = min(data.get('k', 3), 20)
        
        vectorstore_service = VectorstoreService()
        results = vectorstore_service.search(query, k)
        
        return create_success_response({
            "query": query,
            "results_count": len(results),
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return create_error_response("Failed to search documents", 500)

@bp.route('/bulk', methods=['POST'])
@handle_errors
def bulk_add_documents():
    """Bulk add multiple documents"""
    try:
        data = request.get_json()
        if not data or 'documents' not in data:
            return create_error_response("Documents array is required", 400)
        
        documents = data['documents']
        if not isinstance(documents, list) or not documents:
            return create_error_response("Documents must be a non-empty array", 400)
        
        doc_manager = DocumentManager()
        vectorstore_service = VectorstoreService()
        
        result = doc_manager.bulk_add_documents(documents, vectorstore_service)
        
        return create_success_response(result, 201)
        
    except Exception as e:
        logger.error(f"Error bulk adding documents: {e}")
        return create_error_response("Failed to bulk add documents", 500)

@bp.route('/<doc_id>', methods=['DELETE'])
@handle_errors
def delete_document(doc_id):
    """Delete a document and its vectors"""
    try:
        doc_manager = DocumentManager()
        vectorstore_service = VectorstoreService()
        
        result = doc_manager.delete_document(doc_id, vectorstore_service)
        
        if not result['found']:
            return create_error_response("Document not found", 404)
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error deleting document {doc_id}: {e}")
        return create_error_response("Failed to delete document", 500)

@bp.route('/<doc_id>/vectors', methods=['GET'])
@handle_errors
def get_document_vectors(doc_id):
    """Get vectors for a specific document"""
    try:
        vectorstore_service = VectorstoreService()
        vectors = vectorstore_service.get_document_vectors(doc_id)
        
        return create_success_response({
            "doc_id": doc_id,
            "vectors_found": len(vectors),
            "vectors": vectors
        })
        
    except Exception as e:
        logger.error(f"Error getting vectors for doc {doc_id}: {e}")
        return create_error_response("Failed to get document vectors", 500)

@bp.route('/cleanup', methods=['POST'])
@handle_errors
def cleanup_orphaned_vectors():
    """Clean up orphaned vectors"""
    try:
        data = request.get_json()
        dry_run = data.get('dry_run', True) if data else True
        
        doc_manager = DocumentManager()
        vectorstore_service = VectorstoreService()
        
        result = doc_manager.cleanup_orphaned_vectors(vectorstore_service, dry_run)
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")
        return create_error_response("Failed to cleanup orphaned vectors", 500)

@bp.route('/diagnostics', methods=['GET'])
@handle_errors
def document_diagnostics():
    """Get diagnostics for the document system"""
    try:
        doc_manager = DocumentManager()
        vectorstore_service = VectorstoreService()
        
        result = doc_manager.get_diagnostics(vectorstore_service)
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error in diagnostics: {e}")
        return create_error_response("Failed to run diagnostics", 500)

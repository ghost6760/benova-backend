from flask import Blueprint, request, jsonify, send_file
from app.services.openai_service import OpenAIService
from app.services.multiagent_system import MultiAgentSystem
from app.models.conversation import ConversationManager
from app.utils.decorators import handle_errors
from app.utils.helpers import create_success_response, create_error_response
import logging
import tempfile
import os

logger = logging.getLogger(__name__)

bp = Blueprint('multimedia', __name__)

@bp.route('/process-voice', methods=['POST'])
@handle_errors
def process_voice_message():
    """Process voice messages"""
    try:
        if 'audio' not in request.files:
            return create_error_response("No audio file provided", 400)
        
        audio_file = request.files['audio']
        user_id = request.form.get('user_id')
        
        if not user_id:
            return create_error_response("User ID is required", 400)
        
        # Save file temporarily
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                audio_file.save(temp_file.name)
                temp_path = temp_file.name
            
            # Transcribe audio
            openai_service = OpenAIService()
            transcript = openai_service.transcribe_audio(temp_path)
            
            # Process with multi-agent system
            manager = ConversationManager()
            multiagent = MultiAgentSystem()
            
            response, agent_used = multiagent.get_response(
                user_id=user_id,
                question="",
                conversation_manager=manager,
                media_type="voice",
                media_context=transcript
            )
            
            # Convert response to audio if requested
            if request.form.get('return_audio', 'false').lower() == 'true':
                audio_response_path = openai_service.text_to_speech(response)
                return send_file(audio_response_path, mimetype="audio/mpeg")
            
            return create_success_response({
                "transcript": transcript,
                "response": response,
                "agent_used": agent_used
            })
            
        finally:
            # Cleanup temp file
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
        
    except Exception as e:
        logger.error(f"Error processing voice message: {e}")
        return create_error_response("Failed to process voice message", 500)

@bp.route('/process-image', methods=['POST'])
@handle_errors
def process_image_message():
    """Process image messages"""
    try:
        if 'image' not in request.files:
            return create_error_response("No image file provided", 400)
        
        image_file = request.files['image']
        user_id = request.form.get('user_id')
        question = request.form.get('question', '').strip()
        
        if not user_id:
            return create_error_response("User ID is required", 400)
        
        # Analyze image
        openai_service = OpenAIService()
        image_description = openai_service.analyze_image(image_file)
        
        # Process with multi-agent system
        manager = ConversationManager()
        multiagent = MultiAgentSystem()
        
        response, agent_used = multiagent.get_response(
            user_id=user_id,
            question=question,
            conversation_manager=manager,
            media_type="image",
            media_context=image_description
        )
        
        return create_success_response({
            "image_description": image_description,
            "response": response,
            "agent_used": agent_used
        })
        
    except Exception as e:
        logger.error(f"Error processing image message: {e}")
        return create_error_response("Failed to process image message", 500)

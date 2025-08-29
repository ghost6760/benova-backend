from openai import OpenAI
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from flask import current_app
import logging
import requests
import tempfile
import os
import base64
from PIL import Image
import io

logger = logging.getLogger(__name__)

class OpenAIService:
    """Service for OpenAI interactions"""
    
    def __init__(self):
        self.api_key = current_app.config['OPENAI_API_KEY']
        self.model_name = current_app.config['MODEL_NAME']
        self.embedding_model = current_app.config['EMBEDDING_MODEL']
        self.max_tokens = current_app.config['MAX_TOKENS']
        self.temperature = current_app.config['TEMPERATURE']
        self.client = OpenAI(api_key=self.api_key)
    
    def get_chat_model(self):
        """Get LangChain chat model"""
        return ChatOpenAI(
            model_name=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            openai_api_key=self.api_key
        )
    
    def get_embeddings(self):
        """Get LangChain embeddings"""
        return OpenAIEmbeddings(
            model=self.embedding_model,
            openai_api_key=self.api_key
        )
    
    def test_connection(self):
        """Test OpenAI connection"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {e}")
            raise
    
    def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio file to text"""
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            
            return transcript.text if hasattr(transcript, 'text') else str(transcript)
            
        except Exception as e:
            logger.error(f"Error in audio transcription: {e}")
            raise
    
    def transcribe_audio_from_url(self, audio_url: str) -> str:
        """Transcribe audio from URL"""
        temp_path = None
        try:
            logger.info(f"Downloading audio from: {audio_url}")
            
            response = requests.get(audio_url, timeout=60, stream=True)
            response.raise_for_status()
            
            # Determine extension
            extension = '.ogg'  # Default for Chatwoot
            content_type = response.headers.get('content-type', '').lower()
            
            if 'mp3' in content_type or audio_url.endswith('.mp3'):
                extension = '.mp3'
            elif 'wav' in content_type or audio_url.endswith('.wav'):
                extension = '.wav'
            elif 'm4a' in content_type or audio_url.endswith('.m4a'):
                extension = '.m4a'
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                temp_path = temp_file.name
            
            # Transcribe
            return self.transcribe_audio(temp_path)
            
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Could not delete temp file: {e}")
    
    def text_to_speech(self, text: str) -> str:
        """Convert text to speech"""
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text
            )
            
            temp_path = "/tmp/response.mp3"
            response.stream_to_file(temp_path)
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Error in text-to-speech: {e}")
            raise
    
    def analyze_image(self, image_file) -> str:
        """Analyze image using GPT-4 Vision"""
        try:
            # Convert to base64
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": "Describe esta imagen en detalle, enfocándote en elementos relevantes para una consulta de tratamientos estéticos o servicios médicos."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error in image analysis: {e}")
            raise
    
    def analyze_image_from_url(self, image_url: str) -> str:
        """Analyze image from URL"""
        try:
            logger.info(f"Downloading image from: {image_url}")
            
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Create file-like object
            image_file = io.BytesIO(response.content)
            
            return self.analyze_image(image_file)
            
        except Exception as e:
            logger.error(f"Error analyzing image from URL: {e}")
            raise

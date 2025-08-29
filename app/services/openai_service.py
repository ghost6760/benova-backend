from openai import OpenAI
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from flask import current_app
import requests
import tempfile
import os
import logging
from typing import Optional, Dict, Any
from PIL import Image
import io

logger = logging.getLogger(__name__)

def init_openai(app):
    """Initialize OpenAI configuration"""
    try:
        api_key = app.config.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in configuration")
        
        # Test connection
        client = OpenAI(api_key=api_key)
        # Simple test call
        client.models.list()
        
        logger.info("✅ OpenAI connection successful")
        return True
    except Exception as e:
        logger.error(f"❌ OpenAI initialization failed: {e}")
        raise

class OpenAIService:
    """Service for OpenAI API interactions"""
    
    def __init__(self):
        self.api_key = current_app.config['OPENAI_API_KEY']
        self.model_name = current_app.config.get('MODEL_NAME', 'gpt-4o-mini')
        self.embedding_model = current_app.config.get('EMBEDDING_MODEL', 'text-embedding-3-small')
        self.max_tokens = current_app.config.get('MAX_TOKENS', 1500)
        self.temperature = current_app.config.get('TEMPERATURE', 0.7)
        
        self.client = OpenAI(api_key=self.api_key)
        
        # Voice and image enabled flags
        self.voice_enabled = current_app.config.get('VOICE_ENABLED', False)
        self.image_enabled = current_app.config.get('IMAGE_ENABLED', False)
    
    def get_chat_model(self):
        """Get LangChain ChatOpenAI model"""
        return ChatOpenAI(
            api_key=self.api_key,
            model=self.model_name,
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )
    
    def get_embeddings(self):
        """Get LangChain OpenAI embeddings"""
        return OpenAIEmbeddings(
            api_key=self.api_key,
            model=self.embedding_model
        )
    
    def test_connection(self):
        """Test OpenAI connection"""
        try:
            self.client.models.list()
            return True
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {e}")
            raise
    
    def generate_response(self, messages: list, **kwargs) -> str:
        """Generate response using OpenAI Chat API"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature)
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {e}")
            raise
    
    def transcribe_audio(self, audio_file_path: str) -> str:
        """Transcribe audio file to text"""
        if not self.voice_enabled:
            raise ValueError("Voice processing is not enabled")
        
        try:
            with open(audio_file_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="es"
                )
            
            logger.info(f"Audio transcribed successfully: {len(response.text)} chars")
            return response.text
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise
    
    def transcribe_audio_from_url(self, audio_url: str) -> str:
        """Transcribe audio from URL"""
        if not self.voice_enabled:
            raise ValueError("Voice processing is not enabled")
        
        temp_path = None
        try:
            # Download audio file
            response = requests.get(audio_url, timeout=30)
            response.raise_for_status()
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_file.write(response.content)
                temp_path = temp_file.name
            
            # Transcribe
            result = self.transcribe_audio(temp_path)
            return result
            
        except Exception as e:
            logger.error(f"Error transcribing audio from URL: {e}")
            raise
        
        finally:
            # Cleanup temp file
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def analyze_image(self, image_file) -> str:
        """Analyze image using OpenAI Vision API"""
        if not self.image_enabled:
            raise ValueError("Image processing is not enabled")
        
        try:
            # Read image data
            if hasattr(image_file, 'read'):
                image_data = image_file.read()
            else:
                with open(image_file, 'rb') as f:
                    image_data = f.read()
            
            # Convert to base64
            import base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Describe esta imagen en detalle en español, enfocándote en aspectos relevantes para un centro estético."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            raise
    
    def analyze_image_from_url(self, image_url: str) -> str:
        """Analyze image from URL"""
        if not self.image_enabled:
            raise ValueError("Image processing is not enabled")
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Describe esta imagen en detalle en español, enfocándote en aspectos relevantes para un centro estético."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error analyzing image from URL: {e}")
            raise
    
    def text_to_speech(self, text: str) -> str:
        """Convert text to speech and return file path"""
        if not self.voice_enabled:
            raise ValueError("Voice processing is not enabled")
        
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=text[:1000]  # Limit text length
            )
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            temp_file.write(response.content)
            temp_file.close()
            
            logger.info(f"Text-to-speech generated: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            logger.error(f"Error generating speech: {e}")
            raise
    
    def create_embedding(self, text: str) -> list:
        """Create embedding for text"""
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            raise
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get OpenAI service system information"""
        return {
            "model_name": self.model_name,
            "embedding_model": self.embedding_model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "voice_enabled": self.voice_enabled,
            "image_enabled": self.image_enabled,
            "api_key_configured": bool(self.api_key and self.api_key.strip())
        }

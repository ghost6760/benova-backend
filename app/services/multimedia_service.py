# app/services/multimedia_service.py

import os
import tempfile
import requests
import base64
from io import BytesIO
from openai import OpenAI
from typing import Optional
from flask import current_app
import logging

# FIXED: Remove app.core imports that don't exist in modular structure
logger = logging.getLogger(__name__)


class MultimediaService:
    def __init__(self):
        # FIXED: Use current_app.config instead of app.core.config
        self.client = OpenAI(api_key=current_app.config['OPENAI_API_KEY'])
    
    def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio to text using Whisper with Spanish language (EXACTLY like monolith)"""
        try:
            with open(audio_path, "rb") as audio_file:
                # FIXED: Add language="es" like in monolith
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="es",  # MISSING in modular - NOW ADDED
                    response_format="text"
                )
            
            return transcript.text if hasattr(transcript, 'text') else str(transcript)
            
        except Exception as e:
            logger.error(f"Error in audio transcription: {e}")
            raise

    def transcribe_audio_from_url(self, audio_url: str) -> str:
        """Transcribe audio from URL with improved error handling (EXACTLY like monolith)"""
        try:
            logger.info(f"Downloading audio from: {audio_url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; ChatbotAudioTranscriber/1.0)',
                'Accept': 'audio/*,*/*;q=0.9'
            }
            
            response = requests.get(audio_url, headers=headers, timeout=60, stream=True)
            response.raise_for_status()
            
            # Verify content-type if available
            content_type = response.headers.get('content-type', '').lower()
            logger.info(f"Audio content-type: {content_type}")
            
            # Determine extension based on content-type or URL
            extension = '.ogg'  # Default for Chatwoot
            if 'mp3' in content_type or audio_url.endswith('.mp3'):
                extension = '.mp3'
            elif 'wav' in content_type or audio_url.endswith('.wav'):
                extension = '.wav'
            elif 'm4a' in content_type or audio_url.endswith('.m4a'):
                extension = '.m4a'
            
            # Create temporary file with correct extension
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                temp_path = temp_file.name
            
            logger.info(f"Audio saved to temp file: {temp_path} (size: {os.path.getsize(temp_path)} bytes)")
            
            try:
                result = self.transcribe_audio(temp_path)
                logger.info(f"Transcription successful: {len(result)} characters")
                return result
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                    logger.info(f"Temporary file deleted: {temp_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Could not delete temp file {temp_path}: {cleanup_error}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading audio: {e}")
            raise Exception(f"Error downloading audio: {str(e)}")
        except Exception as e:
            logger.error(f"Error in audio transcription from URL: {e}")
            raise

    def analyze_image(self, image_file) -> str:
        """Analyze image using GPT-4 Vision (EXACTLY like monolith)"""
        try:
            # Convert image to base64
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Use correct v1.x syntax
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": "Describe esta imagen en detalle, enfocándote en elementos relevantes para una consulta de tratamientos estéticos o servicios médicos. Si es una promoción o anuncio, menciona los detalles principales."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}",
                                    "detail": "high"  # Added for better analysis
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.1  # More deterministic for analysis
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error in image analysis: {e}")
            raise

    def analyze_image_from_url(self, image_url: str) -> str:
        """Analyze image from URL using GPT-4 Vision (EXACTLY like monolith)"""
        try:
            logger.info(f"Downloading image from: {image_url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; ChatbotImageAnalyzer/1.0)'
            }
            response = requests.get(image_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Verify it's an image
            content_type = response.headers.get('content-type', '').lower()
            if not any(img_type in content_type for img_type in ['image/', 'jpeg', 'png', 'gif', 'webp']):
                logger.warning(f"Content type might not be image: {content_type}")
            
            # Create file in memory
            image_file = BytesIO(response.content)
            
            # Analyze using existing function
            return self.analyze_image(image_file)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading image: {e}")
            raise Exception(f"Error downloading image: {str(e)}")
        except Exception as e:
            logger.error(f"Error in image analysis from URL: {e}")
            raise

    def text_to_speech(self, text: str) -> str:
        """Convert text to audio using OpenAI TTS (EXACTLY like monolith)"""
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text
            )
            
            # Save audio temporarily
            temp_path = "/tmp/response.mp3"
            response.stream_to_file(temp_path)
            
            return temp_path
        except Exception as e:
            logger.error(f"Error in text-to-speech: {e}")
            raise

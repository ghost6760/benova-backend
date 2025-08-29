from app.services.redis_service import get_redis_client
from app.models.conversation import ConversationManager
from app.services.multiagent_system import MultiAgentSystem
from app.services.openai_service import OpenAIService
from flask import current_app
import requests
import logging
import json
import time
import tempfile
import os
import base64
from io import BytesIO
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class ChatwootService:
    """Service for handling Chatwoot interactions with integrated multimedia processing"""

    def __init__(self):
        self.api_key = current_app.config['CHATWOOT_API_KEY']
        self.base_url = current_app.config['CHATWOOT_BASE_URL']
        self.account_id = current_app.config['ACCOUNT_ID']
        self.redis_client = get_redis_client()
        self.bot_active_statuses = ["open"]
        self.bot_inactive_statuses = ["pending", "resolved", "snoozed"]
        
        # Initialize OpenAI service for multimedia processing
        self.openai_service = OpenAIService()

    def send_message(self, conversation_id: int, message_content: str) -> bool:
        """Send message to Chatwoot conversation"""
        url = f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations/{conversation_id}/messages"

        headers = {
            "api_access_token": self.api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "content": message_content,
            "message_type": "outgoing",
            "private": False
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30,
                verify=True
            )

            logger.info(f"Chatwoot API Response Status: {response.status_code}")

            if response.status_code == 200:
                logger.info(f"✅ Message sent to conversation {conversation_id}")
                return True
            else:
                logger.error(f"❌ Failed to send message: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Error sending message to Chatwoot: {e}")
            return False

    def should_bot_respond(self, conversation_id: int, conversation_status: str) -> bool:
        """Determine if bot should respond based on conversation status"""
        self.update_bot_status(conversation_id, conversation_status)
        is_active = conversation_status in self.bot_active_statuses

        if is_active:
            logger.info(f"✅ Bot WILL respond to conversation {conversation_id} (status: {conversation_status})")
        else:
            if conversation_status == "pending":
                logger.info(f"⏸️ Bot will NOT respond to conversation {conversation_id} (status: pending - INACTIVE)")
            else:
                logger.info(f"🚫 Bot will NOT respond to conversation {conversation_id} (status: {conversation_status})")

        return is_active

    def update_bot_status(self, conversation_id: int, conversation_status: str):
        """Update bot status for a specific conversation in Redis"""
        is_active = conversation_status in self.bot_active_statuses

        status_key = f"bot_status:{conversation_id}"
        status_data = {
            'active': str(is_active),
            'status': conversation_status,
            'updated_at': str(time.time())
        }

        try:
            old_status = self.redis_client.hget(status_key, 'active')
            self.redis_client.hset(status_key, mapping=status_data)
            self.redis_client.expire(status_key, 86400)  # 24 hours TTL

            if old_status != str(is_active):
                status_text = "ACTIVO" if is_active else "INACTIVO"
                logger.info(f"🔄 Conversation {conversation_id}: Bot {status_text} (status: {conversation_status})")

        except Exception as e:
            logger.error(f"Error updating bot status in Redis: {e}")

    def is_message_already_processed(self, message_id: int, conversation_id: int) -> bool:
        """Check if message has already been processed"""
        if not message_id:
            return False

        key = f"processed_message:{conversation_id}:{message_id}"

        try:
            if self.redis_client.exists(key):
                logger.info(f"🔄 Message {message_id} already processed, skipping")
                return True

            self.redis_client.set(key, "1", ex=3600)  # 1 hour TTL
            logger.info(f"✅ Message {message_id} marked as processed")
            return False

        except Exception as e:
            logger.error(f"Error checking processed message: {e}")
            return False

    def extract_contact_id(self, data: Dict[str, Any]) -> Tuple[Optional[str], str, bool]:
        """Extract contact_id with unified priority system and validation"""
        conversation_data = data.get("conversation", {})

        # Priority order for contact extraction
        extraction_methods = [
            ("conversation.contact_inbox.contact_id",
             lambda: conversation_data.get("contact_inbox", {}).get("contact_id")),
            ("conversation.meta.sender.id",
             lambda: conversation_data.get("meta", {}).get("sender", {}).get("id")),
            ("root.sender.id",
             lambda: data.get("sender", {}).get("id") if data.get("sender", {}).get("type") != "agent" else None)
        ]

        for method_name, extractor in extraction_methods:
            try:
                contact_id = extractor()
                if contact_id and str(contact_id).strip():
                    # Validate contact_id format
                    contact_id = str(contact_id).strip()
                    if contact_id.isdigit() or contact_id.startswith("contact_"):
                        logger.info(f"✅ Contact ID extracted: {contact_id} (method: {method_name})")
                        return contact_id, method_name, True
            except Exception as e:
                logger.warning(f"Error in extraction method {method_name}: {e}")
                continue

        logger.error("❌ No valid contact_id found in webhook data")
        return None, "none", False

    def handle_conversation_updated(self, data: Dict[str, Any]) -> bool:
        """Handle conversation_updated events"""
        try:
            conversation_id = data.get("id")
            if not conversation_id:
                logger.error("❌ Could not extract conversation_id from conversation_updated event")
                return False

            conversation_status = data.get("status")
            if not conversation_status:
                logger.warning(f"⚠️ No status found in conversation_updated for {conversation_id}")
                return False

            logger.info(f"📋 Conversation {conversation_id} updated to status: {conversation_status}")
            self.update_bot_status(conversation_id, conversation_status)
            return True

        except Exception as e:
            logger.error(f"Error handling conversation_updated: {e}")
            return False

    # INTEGRATED MULTIMEDIA PROCESSING METHODS
    
    def transcribe_audio_from_url(self, audio_url: str) -> str:
        """Transcribe audio from URL with robust error handling (EXACTLY like monolith)"""
        try:
            logger.info(f"🔽 Downloading audio from: {audio_url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; ChatbotAudioTranscriber/1.0)',
                'Accept': 'audio/*,*/*;q=0.9'
            }
            
            response = requests.get(audio_url, headers=headers, timeout=60, stream=True)
            response.raise_for_status()
            
            # Verify content-type if available
            content_type = response.headers.get('content-type', '').lower()
            logger.info(f"📄 Audio content-type: {content_type}")
            
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
            
            logger.info(f"📁 Audio saved to temp file: {temp_path} (size: {os.path.getsize(temp_path)} bytes)")
            
            try:
                result = self.openai_service.transcribe_audio(temp_path)
                logger.info(f"🎵 Transcription successful: {len(result)} characters")
                return result
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                    logger.info(f"🗑️ Temporary file deleted: {temp_path}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Could not delete temp file {temp_path}: {cleanup_error}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error downloading audio: {e}")
            raise Exception(f"Error downloading audio: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error in audio transcription from URL: {e}")
            raise

    def analyze_image_from_url(self, image_url: str) -> str:
        """Analyze image from URL using GPT-4 Vision (EXACTLY like monolith)"""
        try:
            logger.info(f"🔽 Downloading image from: {image_url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; ChatbotImageAnalyzer/1.0)'
            }
            response = requests.get(image_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Verify it's an image
            content_type = response.headers.get('content-type', '').lower()
            if not any(img_type in content_type for img_type in ['image/', 'jpeg', 'png', 'gif', 'webp']):
                logger.warning(f"⚠️ Content type might not be image: {content_type}")
            
            # Create file in memory
            image_file = BytesIO(response.content)
            
            # Analyze using OpenAI service
            return self.openai_service.analyze_image(image_file)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error downloading image: {e}")
            raise Exception(f"Error downloading image: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error in image analysis from URL: {e}")
            raise

    def process_attachment(self, attachment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process Chatwoot attachment with complete parity to monolith"""
        try:
            logger.info(f"Processing Chatwoot attachment: {attachment}")
    
            # Extract type with multiple methods (EXACTLY like monolith)
            attachment_type = None
    
            # Method 1: file_type (most common in Chatwoot)
            if attachment.get("file_type"):
                attachment_type = attachment["file_type"].lower()
                logger.info(f"Type from 'file_type': {attachment_type}")
    
            # Method 2: extension (MISSING in original modular - NOW ADDED)
            elif attachment.get("extension"):
                ext = attachment["extension"].lower().lstrip('.')
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                    attachment_type = "image"
                elif ext in ['mp3', 'wav', 'ogg', 'm4a', 'aac']:
                    attachment_type = "audio"
                logger.info(f"Type inferred from extension '{ext}': {attachment_type}")
    
            # Extract URL with correct priority (EXACTLY like monolith)
            url = attachment.get("data_url") or attachment.get("url") or attachment.get("thumb_url")
    
            if not url:
                logger.warning(f"No URL found in attachment")
                return None
    
            # FIXED: Construct full URL if necessary (MISSING in original modular)
            if not url.startswith("http"):
                # Remove initial slash to avoid double slash
                if url.startswith("/"):
                    url = url[1:]
                url = f"{self.base_url}/{url}"  # self.base_url is CHATWOOT_BASE_URL
                logger.info(f"Full URL constructed: {url}")
    
            # Validate that URL is accessible
            if not url.startswith("http"):
                logger.warning(f"Invalid URL format: {url}")
                return None
    
            return {
                "type": attachment_type,
                "url": url,
                "file_size": attachment.get("file_size", 0),
                "width": attachment.get("width"),
                "height": attachment.get("height"),
                "original_data": attachment
            }
    
        except Exception as e:
            logger.error(f"Error processing Chatwoot attachment: {e}")
            return None

    def debug_webhook_data(self, data: Dict[str, Any]):
        """Complete debugging function exactly like monolith"""
        logger.info("🔍 === WEBHOOK DEBUG INFO ===")
        logger.info(f"Event: {data.get('event')}")
        logger.info(f"Message ID: {data.get('id')}")
        logger.info(f"Message Type: {data.get('message_type')}")
        logger.info(f"Content: '{data.get('content')}'")
        logger.info(f"Content Length: {len(data.get('content', ''))}")

        attachments = data.get('attachments', [])
        logger.info(f"Attachments Count: {len(attachments)}")

        for i, att in enumerate(attachments):
            logger.info(f"  Attachment {i}:")
            logger.info(f"    Keys: {list(att.keys())}")
            logger.info(f"    Type: {att.get('type')}")
            logger.info(f"    File Type: {att.get('file_type')}")
            logger.info(f"    URL: {att.get('url')}")
            logger.info(f"    Data URL: {att.get('data_url')}")
            logger.info(f"    Thumb URL: {att.get('thumb_url')}")

        logger.info("🔍 === END DEBUG INFO ===")

    def process_incoming_message(self, data: Dict[str, Any],
                                 conversation_manager: ConversationManager,
                                 multiagent: MultiAgentSystem) -> Dict[str, Any]:
        """Process incoming message with comprehensive validation and error handling"""
        try:
            # Validate message type
            message_type = data.get("message_type")
            if message_type != "incoming":
                logger.info(f"🤖 Ignoring message type: {message_type}")
                return {"status": "non_incoming_message", "ignored": True}

            # Extract and validate conversation data
            conversation_data = data.get("conversation", {})
            if not conversation_data:
                raise ValueError("Missing conversation data")

            conversation_id = conversation_data.get("id")
            conversation_status = conversation_data.get("status")

            if not conversation_id:
                raise ValueError("Missing conversation ID")

            # Validate conversation_id format
            if not str(conversation_id).strip() or not str(conversation_id).isdigit():
                raise ValueError("Invalid conversation ID format")

            # Check if bot should respond
            if not self.should_bot_respond(conversation_id, conversation_status):
                return {
                    "status": "bot_inactive",
                    "message": f"Bot is inactive for status: {conversation_status}",
                    "active_only_for": self.bot_active_statuses
                }

            # Extract and validate message content
            content = data.get("content", "").strip()
            message_id = data.get("id")

            # MEJORADO: Extraer attachments con debugging
            attachments = data.get("attachments", [])
            logger.info(f"📎 Attachments received: {len(attachments)}")
            for i, att in enumerate(attachments):
                logger.info(f"📎 Attachment {i}: {att}")

            # Check for duplicate processing
            if message_id and self.is_message_already_processed(message_id, conversation_id):
                return {"status": "already_processed", "ignored": True}

            # Extract contact information with improved validation
            contact_id, extraction_method, is_valid = self.extract_contact_id(data)
            if not is_valid or not contact_id:
                raise ValueError("Could not extract valid contact_id from webhook data")

            # Generate standardized user_id
            user_id = conversation_manager._create_user_id(contact_id)

            logger.info(f"🔄 Processing message from conversation {conversation_id}")
            logger.info(f"👤 User: {user_id} (contact: {contact_id}, method: {extraction_method})")
            logger.info(f"💬 Message: {content[:100]}...")

            # ENHANCED: Process multimedia attachments using integrated methods
            media_context = None
            media_type = "text"
            processed_attachment = None

            for attachment in attachments:
                try:
                    logger.info(f"🔍 Processing attachment: {attachment}")
                    processed_attachment = self.process_attachment(attachment)
                    
                    if not processed_attachment:
                        continue
                    
                    attachment_type = processed_attachment.get("type")
                    url = processed_attachment.get("url")
                    
                    if not attachment_type or not url:
                        continue

                    # Process according to type using integrated methods
                    if attachment_type in ["image", "audio"]:
                        media_type = attachment_type
                        
                        logger.info(f"🎯 Processing {media_type}: {url}")

                        if media_type == "audio":
                            try:
                                logger.info(f"🎵 Transcribing audio: {url}")
                                media_context = self.transcribe_audio_from_url(url)
                                logger.info(f"🎵 Audio transcribed: {media_context[:100]}...")
                            except Exception as audio_error:
                                logger.error(f"❌ Audio transcription failed: {audio_error}")
                                media_context = f"[Audio file - transcription failed: {str(audio_error)}]"

                        elif media_type == "image":
                            try:
                                logger.info(f"🖼️ Analyzing image: {url}")
                                media_context = self.analyze_image_from_url(url)
                                logger.info(f"🖼️ Image analyzed: {media_context[:100]}...")
                            except Exception as image_error:
                                logger.error(f"❌ Image analysis failed: {image_error}")
                                media_context = f"[Image file - analysis failed: {str(image_error)}]"

                        break  # Process only the first valid attachment
                    else:
                        logger.info(f"⏭️ Skipping attachment type: {attachment_type}")

                except Exception as e:
                    logger.error(f"❌ Error processing attachment {attachment}: {e}")
                    continue

            # ENHANCED: Validate processable content
            if not content and not media_context:
                logger.error("Empty or invalid message content and no media context")
                debug_info = {
                    "attachments_count": len(attachments),
                    "attachments_sample": attachments[:2] if attachments else [],
                    "content_length": len(content),
                    "media_type": media_type,
                    "processed_attachment": processed_attachment
                }
                logger.error(f"Debug info: {debug_info}")

                return {
                    "status": "success",
                    "message": "Empty message handled",
                    "conversation_id": str(conversation_id),
                    "debug_info": debug_info,
                    "assistant_reply": "Por favor, envía un mensaje con contenido para poder ayudarte. 😊"
                }

            # If only multimedia content without text, use analysis as message
            if not content and media_context:
                content = media_context
                logger.info(f"📝 Using media context as primary content: {media_context[:100]}...")

            # Generate response with multimedia context
            logger.info(f"🤖 Generating response with media_type: {media_type}")
            assistant_reply, agent_used = multiagent.get_response(
                question=content,
                user_id=user_id,
                conversation_manager=conversation_manager,
                media_type=media_type,
                media_context=media_context
            )

            if not assistant_reply or not assistant_reply.strip():
                assistant_reply = "Disculpa, no pude procesar tu mensaje. ¿Podrías intentar de nuevo? 😊"

            logger.info(f"🤖 Assistant response: {assistant_reply[:100]}...")

            # Send response to Chatwoot
            success = self.send_message(conversation_id, assistant_reply)

            if not success:
                raise ValueError("Failed to send response to Chatwoot")

            logger.info(f"✅ Successfully processed message for conversation {conversation_id}")

            return {
                "status": "success",
                "message": "Response sent successfully",
                "conversation_id": str(conversation_id),
                "user_id": user_id,
                "contact_id": contact_id,
                "contact_extraction_method": extraction_method,
                "conversation_status": conversation_status,
                "message_id": message_id,
                "bot_active": True,
                "agent_used": agent_used,
                "message_length": len(content),
                "response_length": len(assistant_reply),
                "media_processed": media_type if media_context else None,
                "media_context_length": len(media_context) if media_context else 0,
                "processed_attachment": processed_attachment
            }

        except Exception as e:
            logger.exception(f"💥 Error procesando mensaje (ID: {data.get('id', 'unknown')})")
            raise

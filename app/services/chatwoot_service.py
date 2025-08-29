from app.services.redis_service import get_redis_client
from app.models.conversation import ConversationManager
from app.services.multiagent_system import MultiAgentSystem
from app.services.openai_service import OpenAIService
from flask import current_app
import requests
import logging
import json
import time
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class ChatwootService:
    """Service for handling Chatwoot interactions"""

    def __init__(self):
        self.api_key = current_app.config['CHATWOOT_API_KEY']
        self.base_url = current_app.config['CHATWOOT_BASE_URL']
        self.account_id = current_app.config['ACCOUNT_ID']
        self.redis_client = get_redis_client()
        self.bot_active_statuses = ["open"]
        self.bot_inactive_statuses = ["pending", "resolved", "snoozed"]

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
        """Extract contact_id from webhook data"""
        conversation_data = data.get("conversation", {})

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

    def process_attachment(self, attachment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process Chatwoot attachment"""
        try:
            logger.info(f"🔍 Processing Chatwoot attachment: {attachment}")

            attachment_type = None

            # Extract type
            if attachment.get("file_type"):
                attachment_type = attachment["file_type"].lower()
            elif attachment.get("extension"):
                ext = attachment["extension"].lower().lstrip('.')
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                    attachment_type = "image"
                elif ext in ['mp3', 'wav', 'ogg', 'm4a', 'aac']:
                    attachment_type = "audio"

            # Extract URL
            url = attachment.get("data_url") or attachment.get("url") or attachment.get("thumb_url")

            if not url:
                logger.warning(f"⚠️ No URL found in attachment")
                return None

            if not url.startswith("http"):
                url = f"{self.base_url}/{url.lstrip('/')}"

            return {
                "type": attachment_type,
                "url": url,
                "file_size": attachment.get("file_size", 0),
                "width": attachment.get("width"),
                "height": attachment.get("height"),
                "original_data": attachment
            }

        except Exception as e:
            logger.error(f"❌ Error processing Chatwoot attachment: {e}")
            return None

    def process_incoming_message(self, data: Dict[str, Any],
                                 conversation_manager: ConversationManager,
                                 multiagent: MultiAgentSystem) -> Dict[str, Any]:
        """Process incoming message from webhook"""
        try:
            # Validate message type
            message_type = data.get("message_type")
            if message_type != "incoming":
                logger.info(f"🤖 Ignoring message type: {message_type}")
                return {"status": "non_incoming_message", "ignored": True}

            # Extract conversation data
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

            # Extract message content and ID
            content = data.get("content", "").strip()
            message_id = data.get("id")

            # Process attachments
            attachments = data.get("attachments", [])
            media_context = None
            media_type = "text"
            processed_attachment = None

            if attachments:
                openai_service = OpenAIService()
                for attachment in attachments:
                    processed = self.process_attachment(attachment)
                    if processed and processed["type"] in ["image", "audio"]:
                        media_type = processed["type"]
                        processed_attachment = processed

                        try:
                            if media_type == "audio":
                                media_context = openai_service.transcribe_audio_from_url(processed["url"])
                            elif media_type == "image":
                                media_context = openai_service.analyze_image_from_url(processed["url"])
                            break
                        except Exception as e:
                            logger.error(f"Error processing {media_type}: {e}")
                            media_context = f"[{media_type.title()} file - processing failed]"

            # Check for duplicate processing
            if message_id and self.is_message_already_processed(message_id, conversation_id):
                return {"status": "already_processed", "ignored": True}

            # Extract contact information
            contact_id, extraction_method, is_valid = self.extract_contact_id(data)
            if not is_valid or not contact_id:
                raise ValueError("Could not extract valid contact_id")

            # Generate user_id
            user_id = conversation_manager._create_user_id(contact_id)

            logger.info(f"🔄 Processing message from conversation {conversation_id}")
            logger.info(f"👤 User: {user_id} (contact: {contact_id})")

            # Handle empty content with media context
            if not content and media_context:
                content = media_context

            if not content:
                return {
                    "status": "success",
                    "message": "Empty message handled",
                    "assistant_reply": "Por favor, envía un mensaje con contenido para poder ayudarte. 😊"
                }

            # Get response from multi-agent system
            assistant_reply, agent_used = multiagent.get_response(
                question=content,
                user_id=user_id,
                conversation_manager=conversation_manager,
                media_type=media_type,
                media_context=media_context
            )

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
                "agent_used": agent_used,
                "media_processed": media_type if media_context else None
            }

        except Exception as e:
            logger.exception(f"Error processing incoming message")
            raise


    def debug_webhook_data(self, data: Dict[str, Any]):
        """Función para debugging completo del webhook de Chatwoot"""
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

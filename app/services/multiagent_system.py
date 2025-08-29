from app.services.openai_service import OpenAIService
from app.services.vectorstore_service import VectorstoreService
from app.models.conversation import ConversationManager
from app.config import Config
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.runnable import RunnableLambda
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.schema.output_parser import StrOutputParser
from flask import current_app
import logging
import json
import requests
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

class MultiAgentSystem:
    """Sistema multi-agente modularizado"""
    
    def __init__(self):
        self.openai_service = OpenAIService()
        self.vectorstore_service = VectorstoreService()
        self.chat_model = self.openai_service.get_chat_model()
        self.retriever = self.vectorstore_service.get_retriever()
        self.conversation_manager = None  # Se inyecta cuando se usa
        
        # Configuración
        self.voice_enabled = current_app.config.get('VOICE_ENABLED', False)
        self.image_enabled = current_app.config.get('IMAGE_ENABLED', False)
        self.schedule_service_url = current_app.config.get('SCHEDULE_SERVICE_URL', 'http://127.0.0.1:4040')
        self.is_local_development = current_app.config.get('ENVIRONMENT') == 'local'
        self.selenium_timeout = 30 if self.is_local_development else 60
        
        # Cache del estado de Selenium
        self.selenium_service_available = False
        self.selenium_status_last_check = 0
        self.selenium_status_cache_duration = 30
        
        # Inicializar agentes
        self.agents = self._initialize_agents()
        
        # Verificar servicio Selenium
        self._initialize_local_selenium_connection()
    
    def _initialize_agents(self):
        """Initialize all specialized agents"""
        return {
            'router': self._create_router_agent(),
            'emergency': self._create_emergency_agent(),
            'sales': self._create_sales_agent(),
            'support': self._create_support_agent(),
            'schedule': self._create_enhanced_schedule_agent(),
            'availability': self._create_availability_agent()
        }
    
    def _verify_selenium_service(self, force_check: bool = False) -> bool:
        """Verificar disponibilidad del servicio Selenium local con cache inteligente"""
        current_time = time.time()
        
        if not force_check and (current_time - self.selenium_status_last_check) < self.selenium_status_cache_duration:
            return self.selenium_service_available
        
        try:
            response = requests.get(
                f"{self.schedule_service_url}/health",
                timeout=3
            )
            
            if response.status_code == 200:
                self.selenium_service_available = True
                self.selenium_status_last_check = current_time
                return True
            else:
                self.selenium_service_available = False
                self.selenium_status_last_check = current_time
                return False
                
        except Exception as e:
            logger.warning(f"Selenium service verification failed: {e}")
            self.selenium_service_available = False
            self.selenium_status_last_check = current_time
            return False
    
    def _initialize_local_selenium_connection(self):
        """Inicializar y verificar conexión con microservicio local"""
        try:
            logger.info(f"Intentando conectar con microservicio de Selenium en: {self.schedule_service_url}")
            
            is_available = self._verify_selenium_service(force_check=True)
            
            if is_available:
                logger.info("✅ Conexión exitosa con microservicio de Selenium local")
            else:
                logger.warning("⚠️ Servicio de Selenium no disponible")
                
        except Exception as e:
            logger.error(f"❌ Error inicializando conexión con Selenium: {e}")
            self.selenium_service_available = False
    
    def _create_router_agent(self):
        """Agente Router: Clasifica la intención del usuario"""
        router_prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres un clasificador de intenciones para Benova (centro estético).

ANALIZA el mensaje del usuario y clasifica la intención en UNA de estas categorías:

1. **EMERGENCY** - Urgencias médicas:
   - Palabras clave: "dolor intenso", "sangrado", "emergencia", "reacción alérgica", "inflamación severa"
   - Síntomas post-tratamiento graves
   - Cualquier situación que requiera atención médica inmediata

2. **SALES** - Consultas comerciales:
   - Información sobre tratamientos
   - Precios y promociones
   - Comparación de procedimientos
   - Beneficios y resultados

3. **SCHEDULE** - Gestión de citas:
   - Agendar citas
   - Modificar citas existentes
   - Cancelar citas
   - Consultar disponibilidad
   - Ver citas programadas
   - Reagendar citas

4. **SUPPORT** - Soporte general:
   - Información general del centro
   - Consultas sobre procesos
   - Cualquier otra consulta

RESPONDE SOLO con el formato JSON:
{{
    "intent": "EMERGENCY|SALES|SCHEDULE|SUPPORT",
    "confidence": 0.0-1.0,
    "keywords": ["palabra1", "palabra2"],
    "reasoning": "breve explicación"
}}

Mensaje del usuario: {question}"""),
            ("human", "{question}")
        ])
        
        return router_prompt | self.chat_model | StrOutputParser()
    
    def _create_emergency_agent(self):
        """Agente de Emergencias: Maneja urgencias médicas"""
        emergency_prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres María, especialista en emergencias médicas de Benova.

SITUACIÓN DETECTADA: Posible emergencia médica.

PROTOCOLO DE RESPUESTA:
1. Expresa empatía y preocupación inmediata
2. Solicita información básica del síntoma
3. Indica que el caso será escalado de emergencia
4. Proporciona información de contacto directo si es necesario

TONO: Profesional, empático, tranquilizador pero urgente.
EMOJIS: Máximo 3 por respuesta.
LONGITUD: Máximo 3 oraciones.

FINALIZA SIEMPRE con: "Escalando tu caso de emergencia ahora mismo. 🚨"

Historial de conversación:
{chat_history}

Mensaje del usuario: {question}"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}")
        ])
        
        return emergency_prompt | self.chat_model | StrOutputParser()
    
    def _create_sales_agent(self):
        """Agente de Ventas: Especializado en información comercial"""
        sales_prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres María, asesora comercial especializada de Benova.

OBJETIVO: Proporcionar información comercial precisa y persuasiva.

INFORMACIÓN DISPONIBLE:
{context}

ESTRUCTURA DE RESPUESTA:
1. Saludo personalizado (si es nuevo cliente)
2. Información del tratamiento solicitado
3. Beneficios principales (máximo 3)
4. Inversión (si disponible)
5. Llamada a la acción para agendar

TONO: Cálido, profesional, persuasivo.
EMOJIS: Máximo 3 por respuesta.
LONGITUD: Máximo 5 oraciones.

FINALIZA SIEMPRE con: "¿Te gustaría agendar tu cita? 📅"

Historial de conversación:
{chat_history}

Pregunta del usuario: {question}"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}")
        ])
        
        def get_sales_context(inputs):
            """Obtener contexto RAG para ventas"""
            try:
                question = inputs.get("question", "")
                self._log_retriever_usage(question, [])
                
                docs = self.retriever.invoke(question)
                self._log_retriever_usage(question, docs)
                
                if not docs:
                    return """Información básica de Benova:
- Centro estético especializado
- Tratamientos de belleza y bienestar
- Atención personalizada
- Profesionales certificados
Para información específica de tratamientos, te conectaré con un especialista."""
                
                return "\n\n".join(doc.page_content for doc in docs)
                
            except Exception as e:
                logger.error(f"Error retrieving sales context: {e}")
                return "Información básica disponible. Te conectaré con un especialista para detalles específicos."
        
        return (
            {
                "context": get_sales_context,
                "question": lambda x: x.get("question", ""),
                "chat_history": lambda x: x.get("chat_history", [])
            }
            | sales_prompt
            | self.chat_model
            | StrOutputParser()
        )
    
    def _create_support_agent(self):
        """Agente de Soporte: Consultas generales y escalación"""
        support_prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres María, especialista en soporte al cliente de Benova.

OBJETIVO: Resolver consultas generales y facilitar navegación.

TIPOS DE CONSULTA:
- Información del centro (ubicación, horarios)
- Procesos y políticas
- Escalación a especialistas
- Consultas generales

INFORMACIÓN DISPONIBLE:
{context}

PROTOCOLO:
1. Respuesta directa a la consulta
2. Información adicional relevante
3. Opciones de seguimiento

TONO: Profesional, servicial, eficiente.
LONGITUD: Máximo 4 oraciones.
EMOJIS: Máximo 3 por respuesta.

Si no puedes resolver completamente: "Te conectaré con un especialista para resolver tu consulta específica. 👩‍⚕️"

Historial de conversación:
{chat_history}

Consulta del usuario: {question}"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}")
        ])
        
        def get_support_context(inputs):
            """Obtener contexto RAG para soporte"""
            try:
                question = inputs.get("question", "")
                self._log_retriever_usage(question, [])
                
                docs = self.retriever.invoke(question)
                self._log_retriever_usage(question, docs)
                
                if not docs:
                    return """Información general de Benova:
- Horarios de atención
- Información general del centro
- Consultas sobre procesos
- Información institucional
Para información específica, te conectaré con un especialista."""
                
                return "\n\n".join(doc.page_content for doc in docs)
                
            except Exception as e:
                logger.error(f"Error retrieving support context: {e}")
                return "Información general disponible. Te conectaré con un especialista para consultas específicas."
        
        return (
            {
                "context": get_support_context,
                "question": lambda x: x.get("question", ""),
                "chat_history": lambda x: x.get("chat_history", [])
            }
            | support_prompt
            | self.chat_model
            | StrOutputParser()
        )
    
    def _create_availability_agent(self):
        """Agente que verifica disponibilidad MEJORADO con comunicación robusta"""
        availability_prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres un agente de disponibilidad de Benova.
    
    ESTADO DEL SISTEMA:
    {selenium_status}
    
    PROTOCOLO:
    1. Verificar estado del servicio Selenium
    2. Extraer la fecha (DD-MM-YYYY) y el tratamiento del mensaje
    3. Consultar el RAG para obtener la duración del tratamiento (en minutos)
    4. Llamar al endpoint /check-availability con la fecha
    5. Filtrar los slots disponibles que puedan acomodar la duración
    6. Devolver los horarios en formato legible
    
    Ejemplo de respuesta:
    "Horarios disponibles para {fecha} (tratamiento de {duracion} min):
    - 09:00 - 10:00
    - 10:30 - 11:30
    - 14:00 - 15:00"
    
    Si no hay disponibilidad: "No hay horarios disponibles para {fecha} con duración de {duracion} minutos."
    Si hay error del sistema: "Error consultando disponibilidad. Te conectaré con un especialista."
    
    Mensaje del usuario: {question}"""),
            ("human", "{question}")
        ])
        
        def get_availability_selenium_status(inputs):
            """Obtener estado del sistema Selenium para availability"""
            is_available = self._verify_selenium_service()
            
            if is_available:
                return f"✅ Sistema de disponibilidad ACTIVO (Conectado a {self.schedule_service_url})"
            else:
                return f"⚠️ Sistema de disponibilidad NO DISPONIBLE (Verificar conexión: {self.schedule_service_url})"
        
        def process_availability(inputs):
            """Procesar consulta de disponibilidad MEJORADA"""
            try:
                question = inputs.get("question", "")
                chat_history = inputs.get("chat_history", [])
                selenium_status = inputs.get("selenium_status", "")
                
                logger.info(f"=== AVAILABILITY AGENT - PROCESANDO ===")
                logger.info(f"Pregunta: {question}")
                logger.info(f"Estado Selenium: {selenium_status}")
                
                if not self._verify_selenium_service():
                    logger.error("Servicio Selenium no disponible para availability agent")
                    return "Error consultando disponibilidad. Te conectaré con un especialista para verificar horarios. 👩‍⚕️"
                
                date = self._extract_date_from_question(question, chat_history)
                treatment = self._extract_treatment_from_question(question)
                
                if not date:
                    return "Por favor especifica la fecha en formato DD-MM-YYYY para consultar disponibilidad."
                
                logger.info(f"Fecha extraída: {date}, Tratamiento: {treatment}")
                
                duration = self._get_treatment_duration(treatment)
                logger.info(f"Duración del tratamiento: {duration} minutos")
                
                availability_data = self._call_check_availability(date)
                
                if not availability_data:
                    logger.warning("No se obtuvieron datos de disponibilidad")
                    return "Error consultando disponibilidad. Te conectaré con un especialista."
                
                if not availability_data.get("available_slots"):
                    logger.info("No hay slots disponibles para la fecha solicitada")
                    return f"No hay horarios disponibles para {date}."
                
                filtered_slots = self._filter_slots_by_duration(
                    availability_data["available_slots"], 
                    duration
                )
                
                logger.info(f"Slots filtrados: {filtered_slots}")
                
                response = self._format_slots_response(filtered_slots, date, duration)
                logger.info(f"=== AVAILABILITY AGENT - RESPUESTA GENERADA ===")
                return response
                
            except Exception as e:
                logger.error(f"Error en agente de disponibilidad: {e}")
                logger.exception("Stack trace completo:")
                return "Error consultando disponibilidad. Te conectaré con un especialista."
    
        return (
            {
                "selenium_status": get_availability_selenium_status,
                "question": lambda x: x.get("question", ""),
                "chat_history": lambda x: x.get("chat_history", [])
            }
            | RunnableLambda(process_availability)
        )
    
    def _create_enhanced_schedule_agent(self):
        """Agente de Schedule mejorado con integración de disponibilidad"""
        schedule_prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres María, especialista en gestión de citas de Benova.
    
    OBJETIVO: Facilitar la gestión completa de citas y horarios usando herramientas avanzadas.
    
    INFORMACIÓN DISPONIBLE:
    {context}
    
    ESTADO DEL SISTEMA DE AGENDAMIENTO:
    {selenium_status}
    
    DISPONIBILIDAD CONSULTADA:
    {available_slots}
    
    FUNCIONES PRINCIPALES:
    - Agendar nuevas citas (con automatización completa via Selenium LOCAL)
    - Modificar citas existentes
    - Cancelar citas
    - Consultar disponibilidad
    - Verificar citas programadas
    - Reagendar citas
    
    PROCESO DE AGENDAMIENTO AUTOMATIZADO:
    1. SIEMPRE verificar disponibilidad PRIMERO
    2. Mostrar horarios disponibles al usuario
    3. Extraer información del paciente del contexto
    4. Validar datos requeridos
    5. Solo usar herramienta de Selenium LOCAL después de confirmar disponibilidad
    6. Confirmar resultado al cliente
    
    DATOS REQUERIDOS PARA AGENDAR:
    - Nombre completo del paciente
    - Número de cédula
    - Teléfono de contacto
    - Fecha deseada
    - Hora preferida (que esté disponible)
    - Fecha de nacimiento (opcional)
    - Género (opcional)
    
    REGLAS IMPORTANTES:
    - NUNCA agendar sin mostrar disponibilidad primero
    - Si no hay disponibilidad, sugerir fechas alternativas
    - Si el horario solicitado no está disponible, mostrar opciones cercanas
    - Confirmar todos los datos antes de proceder
    
    ESTRUCTURA DE RESPUESTA:
    1. Confirmación de la solicitud
    2. Verificación de disponibilidad (OBLIGATORIO)
    3. Información relevante o solicitud de datos faltantes
    4. Resultado de la acción o siguiente paso
    
    TONO: Profesional, eficiente, servicial.
    EMOJIS: Máximo 3 por respuesta.
    LONGITUD: Máximo 6 oraciones.
    
    Historial de conversación:
    {chat_history}
    
    Solicitud del usuario: {question}"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}")
        ])
        
        def get_schedule_context(inputs):
            """Obtener contexto RAG para agenda"""
            try:
                question = inputs.get("question", "")
                self._log_retriever_usage(question, [])
                
                docs = self.retriever.invoke(question)
                self._log_retriever_usage(question, docs)
                
                if not docs:
                    return """Información básica de agenda Benova:
    - Horarios de atención: Lunes a Viernes 8:00 AM - 6:00 PM, Sábados 8:00 AM - 4:00 PM
    - Servicios agendables: Consultas médicas, Tratamientos estéticos, Procedimientos de belleza
    - Políticas de cancelación: 24 horas de anticipación
    - Reagendamiento disponible sin costo
    - Sistema de agendamiento automático con Selenium LOCAL disponible
    - Datos requeridos: Nombre, cédula, teléfono, fecha y hora deseada"""
                
                return "\n\n".join(doc.page_content for doc in docs)
                
            except Exception as e:
                logger.error(f"Error retrieving schedule context: {e}")
                return "Información básica de agenda disponible. Sistema de agendamiento automático disponible."
        
        def get_selenium_status(inputs):
            """Obtener estado del sistema Selenium local usando cache"""
            if self.selenium_service_available:
                return f"✅ Sistema de agendamiento automático ACTIVO (Conectado a {self.schedule_service_url})"
            else:
                return "⚠️ Sistema de agendamiento automático NO DISPONIBLE (Verificar conexión local)"
        
        def process_schedule_with_selenium(inputs):
            """Procesar solicitud de agenda con integración de disponibilidad MEJORADA"""
            try:
                question = inputs.get("question", "")
                user_id = inputs.get("user_id", "default_user")
                chat_history = inputs.get("chat_history", [])
                context = inputs.get("context", "")
                selenium_status = inputs.get("selenium_status", "")
                
                logger.info(f"Procesando solicitud de agenda: {question}")
                
                available_slots = ""
                if self._contains_schedule_intent(question):
                    logger.info("Detectado intent de agendamiento - verificando disponibilidad")
                    try:
                        availability_response = self.agents['availability'].invoke({"question": question})
                        available_slots = availability_response
                        logger.info(f"Disponibilidad obtenida: {available_slots}")
                    except Exception as e:
                        logger.error(f"Error verificando disponibilidad: {e}")
                        available_slots = "Error consultando disponibilidad. Verificaré manualmente."
                
                base_inputs = {
                    "question": question,
                    "chat_history": chat_history,
                    "context": context,
                    "selenium_status": selenium_status,
                    "available_slots": available_slots
                }
                
                logger.info("Generando respuesta base con disponibilidad")
                base_response = (schedule_prompt | self.chat_model | StrOutputParser()).invoke(base_inputs)
                
                should_proceed_selenium = (
                    self._contains_schedule_intent(question) and 
                    self._should_use_selenium(question, chat_history) and
                    self._has_available_slots_confirmation(available_slots) and
                    not self._is_just_availability_check(question)
                )
                
                logger.info(f"¿Proceder con Selenium? {should_proceed_selenium}")
                
                if should_proceed_selenium:
                    logger.info("Procediendo con agendamiento automático via Selenium")
                    selenium_result = self._call_local_schedule_microservice(question, user_id, chat_history)
                    
                    if selenium_result.get('success'):
                        return f"{available_slots}\n\n{selenium_result.get('response', base_response)}"
                    elif selenium_result.get('requires_more_info'):
                        return f"{available_slots}\n\n{selenium_result.get('response', base_response)}"
                    else:
                        return f"{available_slots}\n\n{base_response}\n\nNota: Te conectaré con un especialista para completar el agendamiento."
                
                return base_response
                
            except Exception as e:
                logger.error(f"Error en agendamiento: {e}")
                return "Error procesando tu solicitud. Conectando con especialista... 📋"
        
        return (
            {
                "context": get_schedule_context,
                "selenium_status": get_selenium_status,
                "question": lambda x: x.get("question", ""),
                "chat_history": lambda x: x.get("chat_history", []),
                "user_id": lambda x: x.get("user_id", "default_user")
            }
            | RunnableLambda(process_schedule_with_selenium)
        )
    
    def get_response(self, question: str, user_id: str, conversation_manager: ConversationManager,
                     media_type: str = "text", media_context: str = None) -> Tuple[str, str]:
        """Método principal para obtener respuesta del sistema multi-agente"""
        self.conversation_manager = conversation_manager
        
        if media_type == "image" and media_context:
            processed_question = f"Contexto visual: {media_context}\n\nPregunta: {question}"
        elif media_type == "voice" and media_context:
            processed_question = f"Transcripción de voz: {media_context}\n\nPregunta: {question}"
        else:
            processed_question = question
        
        if not processed_question or not processed_question.strip():
            return "Por favor, envía un mensaje específico para poder ayudarte. 😊", "support"
        
        if not user_id or not user_id.strip():
            return "Error interno: ID de usuario inválido.", "error"
        
        try:
            chat_history = conversation_manager.get_chat_history(user_id, format_type="messages")
            
            inputs = {
                "question": processed_question.strip(), 
                "chat_history": chat_history,
                "user_id": user_id
            }
            
            might_need_rag = self._might_need_rag(processed_question)
            
            logger.info(f"🔍 CONSULTA INICIADA - User: {user_id}, Pregunta: {processed_question[:100]}...")
            if might_need_rag:
                logger.info("   → Posible consulta RAG detectada")
            
            response = self._orchestrate(inputs)
            
            logger.info(f"🤖 RESPUESTA GENERADA - Agente: {self._determine_agent_used(response)}")
            logger.info(f"   → Longitud respuesta: {len(response)} caracteres")
            
            conversation_manager.add_message(user_id, "user", processed_question)
            conversation_manager.add_message(user_id, "assistant", response)
            
            agent_used = self._determine_agent_used(response)
            
            logger.info(f"Multi-agent response generated for user {user_id} using {agent_used}")
            
            return response, agent_used
            
        except Exception as e:
            logger.exception(f"Error en sistema multi-agente (User: {user_id})")
            return "Disculpa, tuve un problema técnico. Por favor intenta de nuevo. 🔧", "error"
    
    def _orchestrate(self, inputs):
        """Orquestador principal que coordina los agentes"""
        try:
            router_response = self.agents['router'].invoke(inputs)
            
            try:
                classification = json.loads(router_response)
                intent = classification.get("intent", "SUPPORT")
                confidence = classification.get("confidence", 0.5)
                
                logger.info(f"Intent classified: {intent} (confidence: {confidence})")
                
            except json.JSONDecodeError:
                intent = "SUPPORT"
                confidence = 0.3
                logger.warning("Router response was not valid JSON, defaulting to SUPPORT")
            
            inputs["user_id"] = inputs.get("user_id", "default_user")
            
            if intent == "EMERGENCY" or confidence > 0.8:
                if intent == "EMERGENCY":
                    return self.agents['emergency'].invoke(inputs)
                elif intent == "SALES":
                    return self.agents['sales'].invoke(inputs)
                elif intent == "SCHEDULE":
                    return self.agents['schedule'].invoke(inputs)
                else:
                    return self.agents['support'].invoke(inputs)
            else:
                return self.agents['support'].invoke(inputs)
                
        except Exception as e:
            logger.error(f"Error in orchestrator: {e}")
            return self.agents['support'].invoke(inputs)
    
    def _extract_date_from_question(self, question, chat_history=None):
        """Extract date from question or chat history"""
        import re
        
        date_str = self._find_date_in_text(question)
        if date_str:
            return date_str
        
        if chat_history:
            history_text = " ".join([
                msg.content if hasattr(msg, 'content') else str(msg) 
                for msg in chat_history
            ])
            date_str = self._find_date_in_text(history_text)
            if date_str:
                return date_str
        
        return None
    
    def _find_date_in_text(self, text):
        """Helper to find date in text"""
        import re
        from datetime import datetime, timedelta
        
        match = re.search(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b', text)
        if match:
            return match.group(0).replace('/', '-')
        
        text_lower = text.lower()
        today = datetime.now()
        
        if "hoy" in text_lower:
            return today.strftime("%d-%m-%Y")
        elif "mañana" in text_lower:
            tomorrow = today + timedelta(days=1)
            return tomorrow.strftime("%d-%m-%Y")
        elif "pasado mañana" in text_lower:
            day_after = today + timedelta(days=2)
            return day_after.strftime("%d-%m-%Y")
        
        return None
    
    def _extract_treatment_from_question(self, question):
        """Extraer tratamiento del mensaje"""
        question_lower = question.lower()
        
        treatments_keywords = {
            "limpieza facial": ["limpieza", "facial", "limpieza facial"],
            "masaje": ["masaje", "masajes", "relajante"],
            "microagujas": ["microagujas", "micro agujas", "microneedling"],
            "botox": ["botox", "toxina"],
            "rellenos": ["relleno", "rellenos", "ácido hialurónico"],
            "peeling": ["peeling", "exfoliación"],
            "radiofrecuencia": ["radiofrecuencia", "rf"],
            "depilación": ["depilación", "láser"]
        }
        
        for treatment, keywords in treatments_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                return treatment
        
        return "tratamiento general"
    
    def _get_treatment_duration(self, treatment):
        """Obtener duración del tratamiento desde RAG o configuración por defecto"""
        try:
            docs = self.retriever.invoke(f"duración tiempo {treatment}")
            
            for doc in docs:
                content = doc.page_content.lower()
                if "duración" in content or "tiempo" in content:
                    import re
                    duration_match = re.search(r'(\d+)\s*(?:minutos?|min)', content)
                    if duration_match:
                        return int(duration_match.group(1))
            
            default_durations = {
                "limpieza facial": 60,
                "masaje": 60,
                "microagujas": 90,
                "botox": 30,
                "rellenos": 45,
                "peeling": 45,
                "radiofrecuencia": 60,
                "depilación": 30,
                "tratamiento general": 60
            }
           
            return default_durations.get(treatment, 60)
           
        except Exception as e:
            logger.error(f"Error obteniendo duración del tratamiento: {e}")
            return 60
    
    def _call_check_availability(self, date):
        """Llamar al endpoint de disponibilidad con la misma lógica que schedule_agent"""
        try:
            if not self._verify_selenium_service():
                logger.warning("Servicio Selenium no disponible para availability check")
                return None
            
            logger.info(f"Consultando disponibilidad en: {self.schedule_service_url}/check-availability para fecha: {date}")
            
            response = requests.post(
                f"{self.schedule_service_url}/check-availability",
                json={"date": date},
                headers={"Content-Type": "application/json"},
                timeout=self.selenium_timeout
            )
            
            logger.info(f"Respuesta de availability endpoint - Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Datos de disponibilidad obtenidos exitosamente: {result.get('success', False)}")
                return result.get("data", {})
            else:
                logger.warning(f"Endpoint de disponibilidad retornó código {response.status_code}")
                logger.warning(f"Respuesta: {response.text}")
                self.selenium_service_available = False
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout conectando con endpoint de disponibilidad ({self.selenium_timeout}s)")
            self.selenium_service_available = False
            return None
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"No se pudo conectar con endpoint de disponibilidad: {self.schedule_service_url}")
            logger.error(f"Error de conexión: {e}")
            logger.error("Verifica que el microservicio esté ejecutándose en tu máquina local")
            self.selenium_service_available = False
            return None
            
        except Exception as e:
            logger.error(f"Error llamando endpoint de disponibilidad: {e}")
            self.selenium_service_available = False
            return None
    
    def _filter_slots_by_duration(self, available_slots, required_duration):
        """Filtrar slots que pueden acomodar la duración requerida"""
        try:
            if not available_slots:
                return []
            
            required_slots = max(1, required_duration // 30)
            
            times = []
            for slot in available_slots:
                if isinstance(slot, dict) and "time" in slot:
                    times.append(slot["time"])
                elif isinstance(slot, str):
                    times.append(slot)
            
            times.sort()
            filtered = []
            
            if required_slots == 1:
                return [f"{time} - {self._add_minutes_to_time(time, required_duration)}" for time in times]
            
            for i in range(len(times) - required_slots + 1):
                consecutive_times = times[i:i + required_slots]
                if self._are_consecutive_times(consecutive_times):
                    start_time = consecutive_times[0]
                    end_time = self._add_minutes_to_time(start_time, required_duration)
                    filtered.append(f"{start_time} - {end_time}")
            
            return filtered
            
        except Exception as e:
            logger.error(f"Error filtrando slots: {e}")
            return []
    
    def _are_consecutive_times(self, times):
        """Verificar si los horarios son consecutivos (diferencia de 30 min)"""
        for i in range(len(times) - 1):
            current_minutes = self._time_to_minutes(times[i])
            next_minutes = self._time_to_minutes(times[i + 1])
            if next_minutes - current_minutes != 30:
                return False
        return True
    
    def _time_to_minutes(self, time_str):
        """Convertir hora a minutos desde medianoche"""
        try:
            time_clean = time_str.strip()
            if ':' in time_clean:
                parts = time_clean.split(':')
                hours = int(parts[0])
                minutes = int(parts[1])
                return hours * 60 + minutes
            return 0
        except (ValueError, IndexError):
            return 0
    
    def _add_minutes_to_time(self, time_str, minutes_to_add):
        """Sumar minutos a una hora y retornar en formato HH:MM"""
        try:
            total_minutes = self._time_to_minutes(time_str) + minutes_to_add
            hours = (total_minutes // 60) % 24
            minutes = total_minutes % 60
            return f"{hours:02d}:{minutes:02d}"
        except:
            return time_str
    
    def _format_slots_response(self, slots, date, duration):
        """Formatear respuesta con horarios disponibles"""
        if not slots:
            return f"No hay horarios disponibles para {date} (tratamiento de {duration} min)."
        
        slots_text = "\n".join(f"- {slot}" for slot in slots)
        return f"Horarios disponibles para {date} (tratamiento de {duration} min):\n{slots_text}"
    
    def _call_local_schedule_microservice(self, question: str, user_id: str, chat_history: list) -> Dict[str, Any]:
        """Llamar al microservicio de schedule LOCAL"""
        try:
            logger.info(f"Llamando a microservicio local en: {self.schedule_service_url}")
            
            response = requests.post(
                f"{self.schedule_service_url}/schedule-request",
                json={
                    "message": question,
                    "user_id": user_id,
                    "chat_history": [
                        {
                            "content": msg.content if hasattr(msg, 'content') else str(msg),
                            "type": getattr(msg, 'type', 'user')
                        } for msg in chat_history
                    ]
                },
                timeout=self.selenium_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success') and result.get('appointment_data'):
                    self._notify_appointment_success(user_id, result.get('appointment_data'))
                
                logger.info(f"Respuesta exitosa del microservicio local: {result.get('success', False)}")
                return result
            else:
                logger.warning(f"Microservicio local retornó código {response.status_code}")
                self.selenium_service_available = False
                return {"success": False, "message": "Servicio local no disponible"}
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout conectando con microservicio local ({self.selenium_timeout}s)")
            self.selenium_service_available = False
            return {"success": False, "message": "Timeout del servicio local"}
        
        except requests.exceptions.ConnectionError:
            logger.error(f"No se pudo conectar con microservicio local: {self.schedule_service_url}")
            logger.error("Verifica que el microservicio esté ejecutándose en tu máquina local")
            self.selenium_service_available = False
            return {"success": False, "message": "Servicio local no disponible"}
        
        except Exception as e:
            logger.error(f"Error llamando microservicio local: {e}")
            self.selenium_service_available = False
            return {"success": False, "message": "Error del servicio local"}
    
    def _contains_schedule_intent(self, question: str) -> bool:
        """Detectar si la pregunta contiene intención de agendamiento"""
        schedule_keywords = [
            "agendar", "reservar", "programar", "cita", "appointment",
            "agenda", "disponibilidad", "horario", "fecha", "hora",
            "procede", "proceder", "confirmar cita"
        ]
        return any(keyword in question.lower() for keyword in schedule_keywords)
    
    def _has_available_slots_confirmation(self, availability_response: str) -> bool:
        """Verificar si la respuesta de disponibilidad contiene slots válidos"""
        if not availability_response:
            return False
        
        availability_lower = availability_response.lower()
        
        text_indicators = [
            "horarios disponibles",
            "disponible para"
        ]
        
        has_text_indicators = any(indicator in availability_lower for indicator in text_indicators)
        has_list_format = "- " in availability_response
        has_time_format = ":" in availability_response and "-" in availability_response
        
        negative_indicators = [
            "no hay horarios disponibles",
            "no hay disponibilidad", 
            "error consultando disponibilidad"
        ]
        
        has_negative = any(indicator in availability_lower for indicator in negative_indicators)
        has_positive = has_text_indicators or has_list_format or has_time_format
        
        return has_positive and not has_negative
    
    def _is_just_availability_check(self, question: str) -> bool:
        """Determinar si solo se está consultando disponibilidad sin agendar"""
        availability_only_keywords = [
            "disponibilidad para", "horarios disponibles", "qué horarios",
            "cuándo hay", "hay disponibilidad", "ver horarios"
        ]
        
        schedule_confirmation_keywords = [
            "agendar", "reservar", "procede", "proceder", "confirmar",
            "quiero la cita", "agenda la cita"
        ]
        
        has_availability_check = any(keyword in question.lower() for keyword in availability_only_keywords)
        has_schedule_confirmation = any(keyword in question.lower() for keyword in schedule_confirmation_keywords)
        
        return has_availability_check and not has_schedule_confirmation
    
    def _should_use_selenium(self, question: str, chat_history: list) -> bool:
        """Determinar si se debe usar el microservicio de Selenium"""
        question_lower = question.lower()
        
        schedule_keywords = [
            "agendar", "reservar", "programar", "cita", "appointment",
            "agenda", "disponibilidad", "horario", "fecha", "hora"
        ]
        
        has_schedule_intent = any(keyword in question_lower for keyword in schedule_keywords)
        has_patient_info = self._extract_patient_info_from_history(chat_history)
        
        return has_schedule_intent and (has_patient_info or self._has_complete_info_in_message(question))
    
    def _extract_patient_info_from_history(self, chat_history: list) -> bool:
        """Extraer información del paciente del historial"""
        history_text = " ".join([msg.content if hasattr(msg, 'content') else str(msg) for msg in chat_history])
        
        has_name = any(word in history_text.lower() for word in ["nombre", "llamo", "soy"])
        has_phone = any(char.isdigit() for char in history_text) and len([c for c in history_text if c.isdigit()]) >= 7
        has_date = any(word in history_text.lower() for word in ["fecha", "día", "mañana", "hoy"])
        
        return has_name and (has_phone or has_date)
    
    def _has_complete_info_in_message(self, message: str) -> bool:
        """Verificar si el mensaje tiene información completa"""
        message_lower = message.lower()
        
        has_name_indicator = any(word in message_lower for word in ["nombre", "llamo", "soy"])
        has_phone_indicator = any(char.isdigit() for char in message) and len([c for c in message if c.isdigit()]) >= 7
        has_date_indicator = any(word in message_lower for word in ["fecha", "día", "mañana", "hoy"])
        
        return has_name_indicator and has_phone_indicator and has_date_indicator
    
    def _notify_appointment_success(self, user_id: str, appointment_data: Dict[str, Any]):
        """Notificar al sistema principal sobre cita exitosa"""
        try:
            main_system_url = os.getenv('MAIN_SYSTEM_URL')
            if main_system_url:
                requests.post(
                    f"{main_system_url}/appointment-notification",
                    json={
                        "user_id": user_id,
                        "event": "appointment_scheduled",
                        "data": appointment_data
                    },
                    timeout=5
                )
                logger.info(f"Notificación enviada al sistema principal para usuario {user_id}")
        except Exception as e:
            logger.error(f"Error notificando cita exitosa: {e}")
    
    def _might_need_rag(self, question: str) -> bool:
        """Determina si una consulta podría necesitar RAG basado en keywords"""
        rag_keywords = [
            "precio", "costo", "inversión", "duración", "tiempo", 
            "tratamiento", "procedimiento", "servicio", "beneficio",
            "horario", "disponibilidad", "agendar", "cita", "información"
        ]
        return any(keyword in question.lower() for keyword in rag_keywords)
    
    def _log_retriever_usage(self, question: str, docs: List) -> None:
        """Log detallado del uso del retriever"""
        if not docs:
            logger.info("   → RAG: No se recuperaron documentos")
            return
        
        logger.info(f"   → RAG: Recuperados {len(docs)} documentos")
        logger.info(f"   → Pregunta: {question[:50]}...")
        
        for i, doc in enumerate(docs[:3]):
            content_preview = doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
            metadata = getattr(doc, 'metadata', {})
            score = getattr(doc, 'score', None)
            
            logger.info(f"   → Doc {i+1}:")
            logger.info(f"      - Contenido: {content_preview}")
            if metadata:
                logger.info(f"      - Metadata: {dict(list(metadata.items())[:3])}...")
            if score is not None:
                logger.info(f"      - Score: {score:.4f}")
    
    def _determine_agent_used(self, response: str) -> str:
        """Determinar qué agente se utilizó basado en la respuesta"""
        if "Escalando tu caso de emergencia" in response:
            return "emergency"
        elif "¿Te gustaría agendar tu cita?" in response:
            return "sales"
        elif "Procesando tu solicitud de agenda" in response:
            return "schedule"
        elif "Te conectaré con un especialista" in response:
            return "support"
        else:
            return "support"
    
    def _log_schedule_decision_process(self, question: str, availability: str, will_use_selenium: bool):
        """Log detallado del proceso de decisión para agendamiento"""
        logger.info(f"=== PROCESO DE DECISIÓN DE AGENDAMIENTO ===")
        logger.info(f"Pregunta: {question}")
        logger.info(f"Disponibilidad obtenida: {bool(availability)}")
        logger.info(f"Slots disponibles: {'Sí' if self._has_available_slots_confirmation(availability) else 'No'}")
        logger.info(f"Usará Selenium: {will_use_selenium}")
        logger.info(f"Solo consulta disponibilidad: {self._is_just_availability_check(question)}")
        logger.info(f"=============================================")
    
    def _handle_selenium_unavailable(self) -> str:
        """Manejar cuando el servicio Selenium no está disponible"""
        return """Lo siento, el sistema de agendamiento automático no está disponible en este momento. 

Puedes:
1. Intentar nuevamente en unos minutos
2. Contactar directamente a nuestro equipo
3. Te conectaré con un especialista para agendar manualmente

¿Prefieres que te conecte con un especialista? 👩‍⚕️"""
    
    def health_check(self) -> Dict[str, Any]:
        """Verificar salud del sistema multi-agente y microservicio LOCAL"""
        try:
            if not self.selenium_service_available:
                service_healthy = self._verify_selenium_service()
            else:
                service_healthy = self.selenium_service_available
            
            return {
                "system_healthy": True,
                "agents_available": ["router", "emergency", "sales", "schedule", "support", "availability"],
                "schedule_service_healthy": service_healthy,
                "schedule_service_url": self.schedule_service_url,
                "schedule_service_type": "LOCAL",
                "system_type": "multi-agent-enhanced",
                "orchestrator_active": True,
                "rag_enabled": True,
                "selenium_integration": service_healthy,
                "environment": os.getenv('ENVIRONMENT', 'production')
            }
        except Exception as e:
            return {
                "system_healthy": True,
                "agents_available": ["router", "emergency", "sales", "schedule", "support", "availability"],
                "schedule_service_healthy": False,
                "schedule_service_url": self.schedule_service_url,
                "schedule_service_type": "LOCAL",
                "system_type": "multi-agent-enhanced",
                "orchestrator_active": True,
                "rag_enabled": True,
                "selenium_integration": False,
                "environment": os.getenv('ENVIRONMENT', 'production'),
                "error": str(e)
            }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del sistema multi-agente"""
        return {
            "agents_available": ["router", "emergency", "sales", "schedule", "support", "availability"],
            "system_type": "multi-agent-enhanced",
            "orchestrator_active": True,
            "rag_enabled": True,
            "selenium_integration": getattr(self, 'selenium_service_available', False),
            "schedule_service_url": self.schedule_service_url,
            "schedule_service_type": "LOCAL",
            "environment": os.getenv('ENVIRONMENT', 'production')
        }
    
    def reconnect_selenium_service(self) -> bool:
        """Método para reconectar con el servicio Selenium local"""
        logger.info("Intentando reconectar con servicio Selenium local...")
        self._initialize_local_selenium_connection()
        return self.selenium_service_available

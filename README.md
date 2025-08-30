# Estructura del Proyecto Benova Backend

## 🏗️ Arquitectura General

Este es un **backend Flask modularizado** para un chatbot de centro estético con las siguientes características:

- **Sistema Multi-Agente** con LangChain y OpenAI
- **Integración con Chatwoot** (webhooks y API)
- **Procesamiento Multimedia** (voz e imágenes)
- **Vectorstore con Redis** y auto-recuperación
- **RAG (Retrieval-Augmented Generation)** para consultas
- **Frontend de pruebas** incluido

## 📁 Estructura de Directorios

```
benova-backend/
├── app/                          # Aplicación principal
│   ├── __init__.py              # Factory pattern y configuración
│   ├── routes/                   # Blueprints por dominio
│   │   ├── __init__.py
│   │   ├── webhook.py           # Webhooks de Chatwoot
│   │   ├── documents.py         # Gestión de documentos/vectores
│   │   ├── conversations.py     # Historial de conversaciones
│   │   ├── health.py           # Health checks del sistema
│   │   ├── multimedia.py       # Procesamiento de audio/imagen
│   │   └── admin.py            # Endpoints administrativos
│   ├── models/                  # Modelos de datos y gestores
│   │   ├── __init__.py
│   │   ├── conversation.py     # Gestión de conversaciones
│   │   ├── document.py         # Gestión de documentos
│   │   └── schemas.py          # Schemas de validación
│   ├── services/               # Lógica de negocio e integraciones
│   │   ├── __init__.py
│   │   ├── chatwoot_service.py        # Integración Chatwoot + multimedia
│   │   ├── openai_service.py          # Servicios OpenAI (Chat, Whisper, Vision)
│   │   ├── redis_service.py           # Conexiones Redis
│   │   ├── vectorstore_service.py     # Gestión de vectores y RAG
│   │   ├── multiagent_system.py       # Sistema multi-agente principal
│   │   ├── multimedia_service.py      # Procesamiento multimedia
│   │   └── vector_auto_recovery.py    # Auto-recuperación vectorstore
│   ├── utils/                  # Utilidades y middlewares
│   │   ├── __init__.py
│   │   ├── validators.py       # Validaciones de entrada
│   │   ├── decorators.py       # Decoradores (errores, auth, cache)
│   │   ├── error_handlers.py   # Manejo de errores
│   │   └── helpers.py         # Funciones auxiliares
│   ├── config/                # Configuración centralizada
│   │   ├── __init__.py
│   │   ├── settings.py        # Configuraciones por entorno
│   │   └── constants.py       # Constantes de la aplicación
│   └── tests/                 # Pruebas unitarias (estructura)
├── migrations/                # Migraciones de base de datos
├── requirements.txt          # Dependencias Python
├── Dockerfile               # Configuración Docker
├── .env.example            # Variables de entorno de ejemplo
├── run.py                  # Servidor de desarrollo
├── wsgi.py                # Punto de entrada WSGI
├── README.md              # Documentación principal
├── index.html             # Frontend de pruebas
├── style.css              # Estilos del frontend
└── script.js              # JavaScript del frontend
```

## 🔧 Componentes Principales

### 1. Sistema Multi-Agente (`multiagent_system.py`)
- **Router Agent**: Clasifica intenciones (emergency, sales, schedule, support)
- **Emergency Agent**: Maneja urgencias médicas
- **Sales Agent**: Información comercial con RAG
- **Support Agent**: Soporte general
- **Schedule Agent**: Gestión de citas con Selenium local
- **Availability Agent**: Consulta disponibilidad de horarios

### 2. Integración Chatwoot (`chatwoot_service.py`)
- Procesamiento de webhooks
- Envío de mensajes
- **Multimedia integrado**: transcripción de audio y análisis de imágenes
- Gestión de estados de conversación
- Extracción de información de contactos

### 3. Vectorstore y RAG (`vectorstore_service.py`)
- Basado en Redis con LangChain
- Chunking inteligente con Markdown y texto
- Búsqueda semántica
- **Auto-recuperación** en caso de corrupción del índice

### 4. Procesamiento Multimedia
- **Audio**: Transcripción con Whisper (Español)
- **Imágenes**: Análisis con GPT-4 Vision
- **Text-to-Speech**: Generación de audio
- Integración completa con Chatwoot

### 5. Gestión de Conversaciones (`conversation.py`)
- Historial con Redis usando LangChain
- Ventana deslizante de mensajes
- Gestión de usuarios de Chatwoot
- Paginación y estadísticas

## 🚀 Tecnologías Utilizadas

### Backend
- **Flask** con factory pattern
- **LangChain** para agentes y RAG
- **OpenAI** (GPT-4, Whisper, DALL-E, Embeddings)
- **Redis** (vectorstore y cache)
- **Gunicorn** (servidor WSGI)

### Integración
- **Chatwoot API** y webhooks
- **Selenium** (microservicio local para agendamiento)
- **Requests** para comunicación HTTP

### Procesamiento
- **Pillow** para imágenes
- **Pydantic** para validación de esquemas
- **Markdown** para procesamiento de documentos

## 📡 Endpoints Principales

### Webhooks
- `POST /webhook/chatwoot` - Recibir eventos de Chatwoot
- `POST /webhook/test` - Pruebas de webhook

### Documentos y RAG
- `POST /documents` - Agregar documento
- `POST /documents/bulk` - Subida masiva
- `GET /documents` - Listar documentos
- `POST /documents/search` - Búsqueda semántica
- `DELETE /documents/{id}` - Eliminar documento

### Conversaciones
- `GET /conversations` - Listar conversaciones
- `GET /conversations/{user_id}` - Obtener conversación
- `POST /conversations/{user_id}/test` - Probar respuesta

### Multimedia
- `POST /multimedia/process-voice` - Procesar audio
- `POST /multimedia/process-image` - Procesar imagen
- `POST /multimedia/test-multimedia` - Pruebas multimedia

### Administración
- `GET /health` - Health check general
- `POST /admin/system/reset` - Reset de caches
- `GET /admin/status` - Estado del sistema

## 🔄 Flujo de Procesamiento

### 1. Webhook de Chatwoot
```
Mensaje → Validación → Extracción multimedia → 
Multi-agente → RAG (si necesario) → Respuesta → Chatwoot
```

### 2. Sistema Multi-Agente
```
Mensaje → Router Agent → Agente Especializado → 
RAG Context (opcional) → Respuesta personalizada
```

### 3. Multimedia
```
Attachment → Download → Processing (Whisper/Vision) → 
Context Integration → Multi-agent response
```

## 🛡️ Características de Seguridad y Robustez

### Auto-Recuperación
- Monitoreo automático del vectorstore
- Reconstrucción de índices corruptos
- Middleware de protección no-bloqueante

### Validación
- Schemas con Pydantic
- Validaciones de entrada robustas
- Manejo centralizado de errores

### Caching
- Redis para caches temporales
- Decorador de caché configurable
- TTL personalizables

## 🌍 Configuración por Entornos

### Development
- Debug habilitado
- Logs detallados
- Selenium local en puerto 4040

### Production
- Optimización Gunicorn
- Error handling robusto
- Health checks completos

### Testing
- Redis DB separada
- Mocks para servicios externos
- Configuración de pruebas

## 📱 Frontend de Pruebas

Incluye un frontend completo en HTML/CSS/JS para:
- Gestión de documentos
- Chat en tiempo real
- Grabación de voz
- Captura de imagen desde cámara
- Subida de archivos multimedia

## 🔌 Integraciones Externas

1. **Chatwoot**: Sistema principal de chat
2. **OpenAI**: Todos los servicios de IA
3. **Redis**: Base de datos y vectorstore
4. **Selenium Local**: Agendamiento automático
5. **Railway**: Despliegue en la nube

Este proyecto representa una **arquitectura moderna y completa** para un chatbot empresarial con capacidades avanzadas de IA, multimedia y automatización.

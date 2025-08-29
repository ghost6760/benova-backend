"""Application constants"""

# Bot status constants
BOT_ACTIVE_STATUSES = ["open"]
BOT_INACTIVE_STATUSES = ["pending", "resolved", "snoozed"]

# Redis key prefixes
REDIS_PREFIXES = {
    "conversation": "conversation:",
    "document": "document:",
    "bot_status": "bot_status:",
    "processed_message": "processed_message:",
    "chat_history": "chat_history:",
    "cache": "cache:",
    "doc_change": "doc_change:"
}

# Redis TTL values (in seconds)
REDIS_TTL = {
    "bot_status": 86400,      # 24 hours
    "processed_message": 3600, # 1 hour
    "conversation": 604800,    # 7 days
    "cache": 300,             # 5 minutes
    "doc_change": 3600        # 1 hour
}

# Multimedia constants
SUPPORTED_IMAGE_TYPES = ['jpg', 'jpeg', 'png', 'gif', 'webp']
SUPPORTED_AUDIO_TYPES = ['mp3', 'wav', 'ogg', 'm4a', 'aac']

# Chunking constants
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
MAX_CHUNK_SIZE = 2000

# Search constants
DEFAULT_SEARCH_K = 3
MAX_SEARCH_K = 20

# Pagination constants
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

# Agent types
AGENT_TYPES = ["router", "emergency", "sales", "support", "schedule", "availability"]

# Treatment durations (in minutes)
TREATMENT_DURATIONS = {
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

# Schedule keywords
SCHEDULE_KEYWORDS = [
    "agendar", "reservar", "programar", "cita", "appointment",
    "agenda", "disponibilidad", "horario", "fecha", "hora",
    "procede", "proceder", "confirmar cita"
]

# Emergency keywords
EMERGENCY_KEYWORDS = [
    "dolor intenso", "sangrado", "emergencia", 
    "reacción alérgica", "inflamación severa"
]

# Sales keywords
SALES_KEYWORDS = [
    "precio", "costo", "inversión", "promoción",
    "tratamiento", "procedimiento", "beneficio"
]

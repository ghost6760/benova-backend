# Benova Backend - Modular Architecture

## 🏗️ Estructura del Proyecto

app/
├── routes/      # Blueprints organizados por dominio
├── models/      # Modelos y esquemas de datos
├── services/    # Lógica de negocio e integraciones
├── utils/       # Helpers y middlewares
├── config/      # Configuración centralizada
└── tests/       # Pruebas unitarias



benova-backend/
├── app/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── webhook.py
│   │   ├── documents.py
│   │   ├── conversations.py
│   │   ├── health.py
│   │   ├── multimedia.py
│   │   └── admin.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── conversation.py
│   │   ├── document.py
│   │   └── schemas.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chatwoot_service.py
│   │   ├── openai_service.py
│   │   ├── redis_service.py
│   │   ├── vectorstore_service.py
│   │   ├── multiagent_system.py
│   │   └── schedule_service.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── validators.py
│   │   ├── decorators.py
│   │   ├── error_handlers.py
│   │   └── helpers.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   └── constants.py
│   └── tests/
│       ├── __init__.py
│       ├── test_routes/
│       ├── test_services/
│       └── test_utils/
├── migrations/
├── requirements.txt
├── Dockerfile
├── .env.example
├── run.py
├── wsgi.py
└── README.md



## 🚀 Inicio Rápido

### Desarrollo Local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env

# Ejecutar en modo desarrollo
export FLASK_ENV=development
python run.py

# Construir imagen
docker build -t benova-backend .

# Ejecutar contenedor
docker run -p 8080:8080 --env-file .env benova-backend


📋 Agregar Nuevas Funcionalidades
1. Nueva Ruta/Endpoint

# app/routes/mi_nuevo_modulo.py
from flask import Blueprint, jsonify
from app.utils.decorators import handle_errors

bp = Blueprint('mi_modulo', __name__)

@bp.route('/test', methods=['GET'])
@handle_errors
def test():
    return jsonify({"message": "Hello World"})

Registrar en app/__init__.py:

from app.routes import mi_nuevo_modulo
app.register_blueprint(mi_nuevo_modulo.bp, url_prefix='/mi-modulo')

2. Nuevo Servicio

# app/services/mi_servicio.py
class MiServicio:
    def __init__(self):
        self.config = current_app.config
    
    def hacer_algo(self):
        # Lógica del servicio
        pass

3. Nuevas Pruebas
# app/tests/test_routes/test_mi_modulo.py
import pytest
from app import create_app
from app.config.settings import TestingConfig

@pytest.fixture
def client():
    app = create_app(TestingConfig)
    with app.test_client() as client:
        yield client

def test_mi_endpoint(client):
    response = client.get('/mi-modulo/test')
    assert response.status_code == 200




CODIGO ORIGINAL app.monolito-original

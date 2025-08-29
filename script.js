// Configuración
const API_BASE = 'https://appopenia-production.up.railway.app/';
let currentUserId = 'test_user';

// Variables globales para multimedia
let mediaRecorder;
let audioChunks = [];
let cameraStream;

// Inicialización
document.addEventListener('DOMContentLoaded', () => {
    loadDocuments();
    setupEventListeners();
});

// Cargar documentos al iniciar
async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE}documents`);
        const data = await response.json();
        
        if (data.status === 'success') {
            renderDocuments(data.documents);
        }
    } catch (error) {
        console.error('Error cargando documentos:', error);
    }
}

// Configurar event listeners
function setupEventListeners() {
    // Formulario de documento individual
    document.getElementById('addDocumentForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const content = document.getElementById('docContent').value;
        const metadata = document.getElementById('docMetadata').value;
        
        try {
            const metadataObj = metadata ? JSON.parse(metadata) : {};
            await addDocument(content, metadataObj);
            await loadDocuments();
            clearForm('addDocumentForm');
            alert('✅ Documento agregado!');
        } catch (error) {
            alert(`❌ Error: ${error.message}`);
        }
    });

    // Formulario de bulk upload
    document.getElementById('bulkUploadForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const files = document.getElementById('bulkFiles').files;
        
        if (!files || files.length === 0) {
            alert('Selecciona al menos un archivo');
            return;
        }
        
        try {
            const documents = await processFiles(files);
            await bulkAddDocuments(documents);
            await loadDocuments();
            document.getElementById('bulkFiles').value = '';
            alert('✅ Archivos subidos!');
        } catch (error) {
            alert(`❌ Error: ${error.message}`);
        }
    });

    // Formulario de chat
    document.getElementById('chatForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = document.getElementById('userMessage').value.trim();
        
        if (!message) return;
        
        try {
            const response = await sendChatMessage(message);
            displayMessage('user', message);
            displayMessage('bot', response);
            document.getElementById('userMessage').value = '';
        } catch (error) {
            alert(`❌ Error: ${error.message}`);
        }
    });

    // Botón para listar documentos y vectores
    document.getElementById('listDocumentsBtn').addEventListener('click', async () => {
        await listDocumentsAndVectors();
    });

    // Botón para limpiar vectores huérfanos
    document.getElementById('cleanupVectorsBtn').addEventListener('click', async () => {
        await cleanupOrphanedVectors();
    });

    // Botón de grabar voz
    document.getElementById('recordVoiceBtn').addEventListener('click', async () => {
        await startVoiceRecording();
    });

    // Botón de parar grabación
    document.getElementById('stopRecordingBtn').addEventListener('click', () => {
        stopVoiceRecording();
    });

    // Botón de capturar imagen
    document.getElementById('captureImageBtn').addEventListener('click', async () => {
        await startCameraCapture();
    });

    // Botón de tomar foto
    document.getElementById('takePictureBtn').addEventListener('click', () => {
        takePicture();
    });

    // Botones del modal de cámara
    document.getElementById('closeCameraBtn').addEventListener('click', () => {
        closeCameraModal();
    });

    document.getElementById('cancelCameraBtn').addEventListener('click', () => {
        closeCameraModal();
    });

    // Handler para archivo de voz (fallback)
    document.getElementById('voiceFile').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        try {
            const response = await sendVoiceMessage(file);
            displayMessage('user', `🎤 Audio: ${file.name}`);
            displayMessage('bot', response);
        } catch (error) {
            alert(`❌ Error: ${error.message}`);
        }
        e.target.value = '';
    });

    // Handler para imagen (fallback)
    document.getElementById('imageFile').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        try {
            const response = await sendImageMessage(file);
            displayMessage('user', `🖼️ Imagen: ${file.name}`);
            displayMessage('bot', response);
        } catch (error) {
            alert(`❌ Error: ${error.message}`);
        }
        e.target.value = '';
    });
}

// Funciones de grabación de voz
async function startVoiceRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const audioFile = new File([audioBlob], 'recording.wav', { type: 'audio/wav' });
            
            try {
                const response = await sendVoiceMessage(audioFile);
                displayMessage('user', '🎤 Mensaje de voz grabado');
                displayMessage('bot', response);
            } catch (error) {
                alert(`❌ Error: ${error.message}`);
            }

            // Limpiar stream
            stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorder.start();
        document.getElementById('recordingStatus').style.display = 'block';
        
    } catch (error) {
        alert('Error accediendo al micrófono: ' + error.message);
    }
}

function stopVoiceRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        document.getElementById('recordingStatus').style.display = 'none';
    }
}

// Funciones de captura de imagen
async function startCameraCapture() {
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({ video: true });
        const video = document.getElementById('cameraVideo');
        video.srcObject = cameraStream;
        
        document.getElementById('cameraModal').style.display = 'block';
        
    } catch (error) {
        alert('Error accediendo a la cámara: ' + error.message);
    }
}

function takePicture() {
    const video = document.getElementById('cameraVideo');
    const canvas = document.getElementById('cameraCanvas');
    const context = canvas.getContext('2d');

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0);

    canvas.toBlob(async (blob) => {
        const imageFile = new File([blob], 'camera_capture.jpg', { type: 'image/jpeg' });
        
        try {
            const response = await sendImageMessage(imageFile);
            displayMessage('user', '📸 Imagen capturada');
            displayMessage('bot', response);
            closeCameraModal();
        } catch (error) {
            alert(`❌ Error: ${error.message}`);
        }
    }, 'image/jpeg', 0.8);
}

function closeCameraModal() {
    document.getElementById('cameraModal').style.display = 'none';
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
}

// Función para enviar mensaje de voz (CORREGIDA)
async function sendVoiceMessage(audioFile) {
    const formData = new FormData();
    formData.append('audio', audioFile);
    formData.append('user_id', currentUserId);

    const response = await fetch(`${API_BASE}multimedia/process-voice`, {
        method: 'POST',
        body: formData
    });
    
    const data = await response.json();
    if (data.status === 'success') {
        return data.response;
    } else {
        throw new Error(data.message || 'Error al procesar audio');
    }
}

// Función para enviar imagen (CORREGIDA)
async function sendImageMessage(imageFile) {
    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('user_id', currentUserId);
    formData.append('question', '¿Qué hay en esta imagen?');

    const response = await fetch(`${API_BASE}multimedia/process-image`, {
        method: 'POST',
        body: formData
    });
    
    const data = await response.json();
    if (data.status === 'success') {
        return data.response;
    } else {
        throw new Error(data.message || 'Error al procesar imagen');
    }
}

// Función para limpiar vectores huérfanos
async function cleanupOrphanedVectors() {
    try {
        const response = await fetch(`${API_BASE}documents/cleanup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dry_run: false })
        });
        
        const data = await response.json();
        if (data.status === 'success') {
            alert(`✅ Limpieza completada: ${data.orphaned_vectors_deleted} vectores eliminados`);
            await loadDocuments();
        } else {
            alert(`❌ Error: ${data.message}`);
        }
    } catch (error) {
        console.error('Error en limpieza:', error);
        alert('Error al limpiar vectores huérfanos');
    }
}

// Función para ver vectores de un documento
async function viewVectors(docId) {
    try {
        const response = await fetch(`${API_BASE}documents/${docId}/vectors`);
        const data = await response.json();
        
        if (data.status === 'success') {
            const vectors = data.vectors;
            let vectorsHtml = `<h4>Vectores para Doc ID: ${docId}</h4>`;
            vectorsHtml += `<p>Total: ${vectors.length} vectores</p>`;
            vectorsHtml += `<ul>`;
            vectors.forEach(vec => {
                vectorsHtml += `<li>Vector Key: ${vec.vector_key}<br>Metadata: ${JSON.stringify(vec.metadata)}</li>`;
            });
            vectorsHtml += `</ul>`;
            
            alert(vectorsHtml);
        } else {
            alert(`❌ Error: ${data.message}`);
        }
    } catch (error) {
        console.error('Error obteniendo vectores:', error);
        alert('Error al obtener vectores');
    }
}

// Agregar documento individual
async function addDocument(content, metadata) {
    const response = await fetch(`${API_BASE}documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, metadata })
    });
    
    if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
    }
}

// Procesar archivos para bulk upload
async function processFiles(files) {
    const documents = [];
    
    for (const file of files) {
        const content = await file.text();
        documents.push({
            content,
            metadata: { filename: file.name, type: file.type }
        });
    }
    
    return documents;
}

// Subir documentos en bulk
async function bulkAddDocuments(documents) {
    const payload = { documents: documents.map(doc => ({ content: doc.content, metadata: doc.metadata })) };
    
    const response = await fetch(`${API_BASE}documents/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
    }
}

// Renderizar lista de documentos
function renderDocuments(documents) {
    const container = document.getElementById('documentsList');
    container.innerHTML = '';
    
    if (documents.length === 0) {
        container.innerHTML = '<p>No hay documentos almacenados</p>';
        return;
    }
    
    documents.forEach((doc, index) => {
        const docElement = document.createElement('div');
        docElement.className = 'document-card';
        docElement.innerHTML = `
            <div class="doc-content">
                <h4>Documento #${index + 1} (ID: ${doc.id})</h4>
                <p><strong>Contenido:</strong> ${doc.content.substring(0, 100)}...</p>
                <p><strong>Metadata:</strong> ${JSON.stringify(doc.metadata)}</p>
                <p><strong>Chunks:</strong> ${doc.chunk_count}</p>
            </div>
            <div class="doc-actions">
                <button class="view-vectors-btn" data-doc-id="${doc.id}">Ver Vectores</button>
                <button class="delete-btn" data-doc-id="${doc.id}">🗑️ Eliminar</button>
            </div>
        `;
        container.appendChild(docElement);
    });
    
    // Agregar event listeners para ver vectores y eliminar
    document.querySelectorAll('.view-vectors-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const docId = e.target.getAttribute('data-doc-id');
            viewVectors(docId);
        });
    });
    
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const docId = e.target.getAttribute('data-doc-id');
            if (confirm(`¿Estás seguro de eliminar el documento con ID ${docId}?`)) {
                await deleteDocument(docId);
                await loadDocuments();
            }
        });
    });
}

// Listar documentos y vectores
async function listDocumentsAndVectors() {
    try {
        const response = await fetch(`${API_BASE}documents`);
        const data = await response.json();
        
        if (data.status === 'success') {
            const documents = data.documents;
            renderDocuments(documents);
        }
    } catch (error) {
        console.error('Error listando documentos y vectores:', error);
        alert('Error al listar documentos y vectores');
    }
}

// Eliminar documento
async function deleteDocument(docId) {
    try {
        const response = await fetch(`${API_BASE}documents/${docId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (data.status === 'success') {
            alert('✅ Documento eliminado correctamente');
        } else {
            alert(`❌ Error: ${data.message}`);
        }
    } catch (error) {
        console.error('Error eliminando documento:', error);
        alert('Error al eliminar el documento');
    }
}

// Enviar mensaje al chatbot
async function sendChatMessage(message) {
    const response = await fetch(`${API_BASE}conversations/${currentUserId}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
    });
    
    const data = await response.json();
    if (data.status === 'success') {
        return data.bot_response;
    } else {
        throw new Error(data.message || 'Error al obtener respuesta');
    }
}

// Mostrar mensaje en el chat
function displayMessage(role, message) {
    const chatContainer = document.getElementById('chatHistory');
    const messageElement = document.createElement('div');
    messageElement.className = `message ${role}-message`;
    messageElement.textContent = message;
    chatContainer.appendChild(messageElement);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Limpiar formulario
function clearForm(formId) {
    const form = document.getElementById(formId);
    form.reset();
}

import os
import fitz  # PyMuPDF
import docx
import sqlite3
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import cloudinary
import cloudinary.uploader
from transformers import pipeline

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Cloudinary config
cloudinary.config(
    cloud_name="dc2jtiedu",
    api_key="398344752441678",
    api_secret="49zrADzUKpP2JlKRDfzxBCOObfI",
    secure=True
)

# FastAPI init
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["192.168.1.3"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create SQLite DB if not exists
conn = sqlite3.connect("documents.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    file_url TEXT,
    category TEXT,
    summary TEXT,
    flashcards TEXT
)
""")
conn.commit()
conn.close()

# HuggingFace summarizer
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

# Flashcard generator básico
def generate_study_plan(text):
    summary = summarizer(text[:1024], max_length=300, min_length=100, do_sample=False)[0]['summary_text']
    flashcards = "\n".join([
        f"Pregunta {i+1}: ¿Qué significa '{word}'?"
        for i, word in enumerate(text.split()[:5])
    ])
    return summary, flashcards

# Subida de archivo
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    print("Recibiendo archivo...")

    file_ext = os.path.splitext(file.filename)[1].lower()
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    # Guardar archivo localmente
    with open(file_path, "wb") as f:
        f.write(await file.read())

    print(f"Guardado local: {file_path}")

    # Subir a Cloudinary
    upload_result = cloudinary.uploader.upload_large(file_path, resource_type="raw")
    file_url = upload_result['secure_url']
    print(f"Subido a Cloudinary: {file_url}")

    # Extraer texto
    extracted_text = ""
    if file_ext == ".pdf":
        with fitz.open(file_path) as doc:
            for page in doc:
                extracted_text += page.get_text()
    elif file_ext == ".docx":
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            extracted_text += para.text + "\n"
    else:
        return {"error": "Formato no compatible"}

    print("Texto extraído")

    # Categoría dummy por ahora
    category = "Categoría de ejemplo"

    # Generar resumen y flashcards
    summary, flashcards = generate_study_plan(extracted_text)

    # Guardar en SQLite
    conn = sqlite3.connect("documents.db")
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO documents (filename, file_url, category, summary, flashcards)
    VALUES (?, ?, ?, ?, ?)
    """, (file.filename, file_url, category, summary, flashcards))
    conn.commit()
    conn.close()

    return {
        "filename": file.filename,
        "file_url": file_url,
        "category": category,
        "summary": summary,
        "flashcards": flashcards,
        "message": "Archivo recibido y procesado correctamente"
    }

# Endpoint para historial

from fastapi.responses import JSONResponse
import sqlite3

@app.get("/historial")
def get_historial():
    conn = sqlite3.connect("historial.db")
    cursor = conn.cursor()
    cursor.execute("SELECT filename, category, file_url, resumen, flashcards, created_at FROM historial ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()

    historial = []
    for row in rows:
        historial.append({
            "filename": row[0],
            "category": row[1],
            "file_url": row[2],
            "summary": row[3],
            "flashcards": row[4],
            "created_at": row[5]
        })
    return JSONResponse(content={"historial": historial})

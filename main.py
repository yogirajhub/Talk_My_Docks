from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import shutil
import os
import requests
import uuid
from dotenv import load_dotenv
from gtts import gTTS
from pypdf import PdfReader

app = FastAPI()

# -------- Load ENV variables --------
load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
API_URL = os.getenv("GROQ_API_URL")
MODEL = os.getenv("LLM_MODEL")

# -------- Folders --------
UPLOAD_FOLDER = "uploads"
AUDIO_FOLDER = "audio"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/audio", StaticFiles(directory="audio"), name="audio")

stored_text = ""

# -------- Helper Function to Read PDF --------
def read_pdf(file_path):

    reader = PdfReader(file_path)
    text = ""

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text

    return text


# -------- LLM Function --------
def ask_llm(question, context):

    # limit context (LLM token safety)
    context = context[:3000]

    prompt = f"""
Use the following document to answer the question.

Document:
{context}

Question:
{question}

Answer clearly.
"""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3
    }

    response = requests.post(API_URL, headers=headers, json=data)

    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)

    if response.status_code != 200:
        return "LLM API error."

    result = response.json()

    return result["choices"][0]["message"]["content"]


# -------- Upload Page --------
@app.get("/", response_class=HTMLResponse)
def upload_page(request: Request):

    return templates.TemplateResponse(
        "upload.html",
        {"request": request}
    )


# -------- File Upload --------
@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):

    global stored_text

    file_path = f"{UPLOAD_FOLDER}/{file.filename}"

    # save uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # detect file type
    if file.filename.endswith(".pdf"):

        stored_text = read_pdf(file_path)

    else:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                stored_text = f.read()

        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1") as f:
                stored_text = f.read()

    return templates.TemplateResponse(
        "ask.html",
        {"request": request}
    )


# -------- Ask Question --------
@app.post("/ask", response_class=HTMLResponse)
async def ask_question(request: Request, question: str = Form(...)):

    global stored_text

    if stored_text == "":
        answer = "Please upload a document first."
    else:
        answer = ask_llm(question, stored_text)

    # -------- Text to Speech --------
    tts = gTTS(answer)

    filename = f"{uuid.uuid4()}.mp3"
    audio_path = f"{AUDIO_FOLDER}/{filename}"

    tts.save(audio_path)

    return templates.TemplateResponse(
        "ask.html",
        {
            "request": request,
            "answer": answer,
            "audio": f"/audio/{filename}"
        }
    )
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
STORAGE_DIR = BASE_DIR / "storage"
SKILLS_DIR = BASE_DIR / "skills" / "custom"
AUDIO_CACHE_DIR = BASE_DIR / "cache" / "audio"
MODELS_DIR = PROJECT_ROOT / "models"

STORAGE_DIR.mkdir(parents=True, exist_ok=True)
SKILLS_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

class Config:
    HOST = os.getenv("HEXOR_HOST", "127.0.0.1")
    PORT = int(os.getenv("HEXOR_PORT", "8000"))
    
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
    
    VOICE_NAME = os.getenv("VOICE_NAME", "en-GB-RyanNeural")
    VOICE_RATE = os.getenv("VOICE_RATE", "+0%")
    VOICE_PITCH = os.getenv("VOICE_PITCH", "-4Hz")
    
    BAMBU_IP = os.getenv("BAMBU_IP", "")
    BAMBU_SERIAL = os.getenv("BAMBU_SERIAL", "")
    BAMBU_ACCESS_CODE = os.getenv("BAMBU_ACCESS_CODE", "")

    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/api/spotify/callback")
    
    ASSISTANT_NAME = "Hexor"
    USER_TITLE = os.getenv("USER_TITLE", "Sir")

config = Config()

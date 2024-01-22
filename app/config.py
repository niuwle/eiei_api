# app/config.py
import os
from dotenv import load_dotenv
load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")
OPENROUTER_TOKEN = os.getenv("OPENROUTER_TOKEN")
TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")
TELEGRAM_API_URL = os.getenv("TELEGRAM_API_URL")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")
OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
ASSISTANT_PROMPT = os.getenv("ASSISTANT_PROMPT")

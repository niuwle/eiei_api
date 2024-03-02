# app/config.py
import os
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")
OPENROUTER_TOKEN = os.getenv("OPENROUTER_TOKEN")
TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")
TELEGRAM_API_URL = os.getenv("TELEGRAM_API_URL")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")
OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
ASSISTANT_PROMPT = os.getenv("ASSISTANT_PROMPT")
MONSTER_API_TOKEN = os.getenv("MONSTER_API_TOKEN")
HUGGINGFACE_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")
ELEVENLABS_KEY = os.getenv("ELEVENLABS_KEY") 
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")

HOST_URL = os.getenv("HOST_URL")
CREDIT_COST_PHOTO = Decimal(os.getenv("CREDIT_COST_PHOTO", "10"))* Decimal('-1')
CREDIT_COST_AUDIO = Decimal(os.getenv("CREDIT_COST_AUDIO", "5"))* Decimal('-1')
CREDIT_COST_TEXT = Decimal(os.getenv("CREDIT_COST_TEXT", "1"))* Decimal('-1')


B2_APPLICATION_KEY_ID = os.getenv("B2_APPLICATION_KEY_ID") 
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
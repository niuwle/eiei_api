# ./app/utils/request_classifier.py
import logging
import spacy
from app.controllers.telegram_integration import send_request_for_audio, send_request_for_photo

logger = logging.getLogger(__name__)
# Load your trained spaCy model
nlp = spacy.load("./spacy_model")

async def is_voice_note_request(text):
    """
    Determines if the text is a voice note request.
    
    Parameters:
    text (str): The text to classify.
    
    Returns:
    bool: True if the text is a voice note request, False otherwise.
    """
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "VOICE_NOTE_REQUEST":
            logger.debug("Voice request true")
            return True
    logger.debug("Voice request false")
    return False

async def is_photo_request(text):
    """
    Determines if the text is a photo request.
    
    Parameters:
    text (str): The text to classify.
    
    Returns:
    bool: True if the text is a photo request, False otherwise.
    """
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "PHOTO_REQUEST":
            logger.debug("Photo request true")
            return True
    logger.debug("Photo request false")
    return False


async def check_intent(  content_text: str,  chat_id: int, bot_token: str
    ):
    if await is_voice_note_request(content_text):
        await send_request_for_audio(chat_id,bot_token)
    elif await is_photo_request(content_text):
        await send_request_for_photo(chat_id,bot_token)
    else:
        logging.debug("No specific request identified.")

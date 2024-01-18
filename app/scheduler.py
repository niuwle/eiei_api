# app/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.controllers.message_processing import check_new_messages

def setup_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_new_messages, 'interval', seconds=5)
    scheduler.start()

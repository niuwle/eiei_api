from fastapi import APIRouter

router = APIRouter()

@router.get("/keep-alive")
async def keep_alive():
    """
    A simple endpoint to keep the web service alive by making lightweight requests.
    """
    return {"message": "Service is alive."}

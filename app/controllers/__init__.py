from fastapi import APIRouter

router = APIRouter()

# Example route
@router.get("/")
async def root():
    return {"message": "Hello World"}

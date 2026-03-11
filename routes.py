from fastapi import APIRouter
from src.Joe_ai_bot import joe
from src.Sara_ai_bot import sara
from src.Red_ai_bot import red
from src.Blue_ai_bot import blue
from src.White_ai_bot import white
from src.Yellow_ai_bot import yellow
from pydantic import BaseModel



router = APIRouter()



class BotRequestModel(BaseModel):
    user_input: str
    relationship_context: bool = False
    engagement_context: dict = None




@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/routes-info")
async def routes_info():
    return {
        "routes": [
            {"path": "/chat/joe", "method": "POST"},
            {"path": "/chat/sara", "method": "POST"},
            {"path": "/chat/red", "method": "POST"},
            {"path": "/chat/blue", "method": "POST"},
            {"path": "/chat/white", "method": "POST"},
            {"path": "/chat/yellow", "method": "POST"},
        ]
    }


@router.post("/chat/sara")
async def chat_sara(user_input: BotRequestModel = None):
    return {"response": sara(user_input.user_input, relationship_context=user_input.relationship_context, engagement_context=user_input.engagement_context)}


@router.post("/chat/red")
async def chat_red(user_input: BotRequestModel = None):
    return {"response": red(user_input.user_input, relationship_context=user_input.relationship_context, engagement_context=user_input.engagement_context)}


@router.post("/chat/blue")
async def chat_blue(user_input: BotRequestModel = None):
    return {"response": blue(user_input.user_input, relationship_context=user_input.relationship_context, engagement_context=user_input.engagement_context)}


@router.post("/chat/white")
async def chat_white(user_input: BotRequestModel = None):
    return {"response": white(user_input.user_input, relationship_context=user_input.relationship_context, engagement_context=user_input.engagement_context)}


@router.post("/chat/yellow")
async def chat_yellow(user_input: BotRequestModel = None):
    return {"response": yellow(user_input.user_input, relationship_context=user_input.relationship_context, engagement_context=user_input.engagement_context)}


@router.post("/chat/joe")
async def chat_joe(user_input: BotRequestModel = None):
    return {"response": joe(user_input.user_input, relationship_context=user_input.relationship_context, engagement_context=user_input.engagement_context)}
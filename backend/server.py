import os
import logging
import uuid
import uvicorn
from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

# 1. Initialize Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# 2. Safe Environment Variables
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'media_hub')

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

app = FastAPI()
api_router = APIRouter(prefix="/api")

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class Shortcut(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    url: str
    color: str = "#D31A38"
    logo_url: Optional[str] = None
    is_preset: bool = False
    position: int = 0
    created_at: str = Field(default_factory=now_iso)
    deleted_at: Optional[str] = None

class ShortcutCreate(BaseModel):
    title: str
    url: str
    color: str = "#D31A38"
    logo_url: Optional[str] = None

class ShortcutUpdate(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    color: Optional[str] = None
    logo_url: Optional[str] = None

PRESETS = [
    {"title": "YouTube", "url": "https://www.youtube.com", "color": "#FF0000", "logo_url": "https://logo.clearbit.com/youtube.com", "position": 0},
    {"title": "JioHotstar", "url": "https://www.hotstar.com", "color": "#1F80E0", "logo_url": "https://logo.clearbit.com/hotstar.com", "position": 1},
    {"title": "Netflix", "url": "https://www.netflix.com", "color": "#E50914", "logo_url": "https://logo.clearbit.com/netflix.com", "position": 2},
    {"title": "Prime Video", "url": "https://www.primevideo.com", "color": "#1399FF", "logo_url": "https://logo.clearbit.com/primevideo.com", "position": 3},
]

def clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc

@app.on_event("startup")
async def seed_presets():
    try:
        for preset in PRESETS:
            existing = await db.shortcuts.find_one({"title": preset["title"], "is_preset": True})
            if not existing:
                sc = Shortcut(is_preset=True, **preset)
                await db.shortcuts.insert_one(sc.dict())
        logger.info("Preset shortcuts ensured")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")

@api_router.get("/")
async def root():
    return {"message": "Media Hub API"}

@api_router.get("/shortcuts", response_model=List[Shortcut])
async def list_shortcuts():
    docs = await db.shortcuts.find({"deleted_at": None}).sort("position", 1).to_list(500)
    return [Shortcut(**clean(d)) for d in docs]

@api_router.post("/shortcuts", response_model=Shortcut)
async def create_shortcut(payload: ShortcutCreate):
    count = await db.shortcuts.count_documents({"deleted_at": None})
    sc = Shortcut(position=count, **payload.dict())
    await db.shortcuts.insert_one(sc.dict())
    return sc

@api_router.patch("/shortcuts/{shortcut_id}", response_model=Shortcut)
async def update_shortcut(shortcut_id: str, payload: ShortcutUpdate):
    doc = await db.shortcuts.find_one({"id": shortcut_id, "deleted_at": None})
    if not doc:
        raise HTTPException(status_code=404, detail="Shortcut not found")
    updates = {k: v for k, v in payload.dict().items() if v is not None}
    if updates:
        await db.shortcuts.update_one({"id": shortcut_id}, {"$set": updates})
    doc = await db.shortcuts.find_one({"id": shortcut_id})
    return Shortcut(**clean(doc))

@api_router.delete("/shortcuts/{shortcut_id}")
async def delete_shortcut(shortcut_id: str):
    doc = await db.shortcuts.find_one({"id": shortcut_id, "deleted_at": None})
    if not doc:
        raise HTTPException(status_code=404, detail="Shortcut not found")
    await db.shortcuts.update_one({"id": shortcut_id}, {"$set": {"deleted_at": now_iso()}})
    return {"success": True, "id": shortcut_id}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# 3. Server Startup Block
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

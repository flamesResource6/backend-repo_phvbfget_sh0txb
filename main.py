import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db

app = FastAPI(title="Durarara MVP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TENANT_DEFAULT = "default"

# Utilities
class Obj(BaseModel):
    id: str

def to_str_id(doc: dict) -> dict:
    if not doc:
        return doc
    d = {**doc}
    _id = d.pop("_id", None)
    if isinstance(_id, ObjectId):
        d["id"] = str(_id)
    elif _id is not None:
        d["id"] = str(_id)
    return d

# Schemas (importing for type hints)
from schemas import Persona as PersonaSchema, Room as RoomSchema, Message as MessageSchema, Alert as AlertSchema, RoomMember as RoomMemberSchema

# Startup bootstrap: ensure a Global room exists
@app.on_event("startup")
def ensure_global_room():
    if db is None:
        return
    col = db["room"]
    existing = col.find_one({"tenant_id": TENANT_DEFAULT, "type": "global", "name": "Global"})
    if not existing:
        now = datetime.now(timezone.utc)
        col.insert_one({
            "tenant_id": TENANT_DEFAULT,
            "name": "Global",
            "type": "global",
            "member_count": 0,
            "created_at": now,
            "updated_at": now,
        })

@app.get("/")
def read_root():
    return {"message": "Durarara API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available" if db is None else "✅ Connected & Working",
        "collections": []
    }
    try:
        if db is not None:
            response["collections"] = db.list_collection_names()
    except Exception as e:
        response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
    return response

# Personas
class PersonaCreate(BaseModel):
    handle: str
    color: Optional[str] = "#7c3aed"
    bio: Optional[str] = None
    avatar_letter: Optional[str] = None

@app.get("/api/personas")
def list_personas(tenant_id: str = TENANT_DEFAULT):
    if db is None:
        raise HTTPException(500, "Database not configured")
    items = [to_str_id(p) for p in db["persona"].find({"tenant_id": tenant_id}).limit(200)]
    return items

@app.post("/api/personas")
def create_persona(payload: PersonaCreate, tenant_id: str = TENANT_DEFAULT):
    if db is None:
        raise HTTPException(500, "Database not configured")
    # unique handle per tenant
    exists = db["persona"].find_one({"tenant_id": tenant_id, "handle": payload.handle})
    if exists:
        raise HTTPException(400, "Handle already taken")
    now = datetime.now(timezone.utc)
    doc = {
        "tenant_id": tenant_id,
        "handle": payload.handle,
        "color": payload.color,
        "bio": payload.bio,
        "avatar_letter": payload.avatar_letter or (payload.handle[:1].upper() if payload.handle else "?"),
        "trust_level": 1,
        "score_thanks": 0,
        "score_helpful": 0,
        "created_at": now,
        "updated_at": now,
        "is_banned": False,
    }
    res = db["persona"].insert_one(doc)
    return {"id": str(res.inserted_id), **doc}

# Rooms
class RoomCreate(BaseModel):
    name: str
    type: str = "topic"  # global|city|topic|private
    city: Optional[str] = None
    topic: Optional[str] = None

@app.get("/api/rooms")
def list_rooms(tenant_id: str = TENANT_DEFAULT):
    if db is None:
        raise HTTPException(500, "Database not configured")
    items = [to_str_id(r) for r in db["room"].find({"tenant_id": tenant_id}).limit(200)]
    return items

@app.post("/api/rooms")
def create_room(payload: RoomCreate, tenant_id: str = TENANT_DEFAULT):
    if db is None:
        raise HTTPException(500, "Database not configured")
    now = datetime.now(timezone.utc)
    doc = {
        "tenant_id": tenant_id,
        "name": payload.name,
        "type": payload.type,
        "city": payload.city,
        "topic": payload.topic,
        "member_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    res = db["room"].insert_one(doc)
    return {"id": str(res.inserted_id), **doc}

class JoinLeave(BaseModel):
    persona_id: str

@app.post("/api/rooms/{room_id}/join")
def join_room(room_id: str, payload: JoinLeave, tenant_id: str = TENANT_DEFAULT):
    if db is None:
        raise HTTPException(500, "Database not configured")
    try:
        rid = ObjectId(room_id)
        pid = ObjectId(payload.persona_id)
    except Exception:
        raise HTTPException(400, "Invalid ids")
    room = db["room"].find_one({"_id": rid, "tenant_id": tenant_id})
    if not room:
        raise HTTPException(404, "Room not found")
    persona = db["persona"].find_one({"_id": pid, "tenant_id": tenant_id})
    if not persona:
        raise HTTPException(404, "Persona not found")
    now = datetime.now(timezone.utc)
    db["roommember"].update_one(
        {"tenant_id": tenant_id, "room_id": room_id, "persona_id": payload.persona_id},
        {"$setOnInsert": {"joined_at": now}}, upsert=True,
    )
    db["room"].update_one({"_id": rid}, {"$inc": {"member_count": 1}, "$set": {"updated_at": now}})
    return {"ok": True}

@app.post("/api/rooms/{room_id}/leave")
def leave_room(room_id: str, payload: JoinLeave, tenant_id: str = TENANT_DEFAULT):
    if db is None:
        raise HTTPException(500, "Database not configured")
    db["roommember"].delete_one({"tenant_id": tenant_id, "room_id": room_id, "persona_id": payload.persona_id})
    db["room"].update_one({"_id": ObjectId(room_id)}, {"$inc": {"member_count": -1}, "$set": {"updated_at": datetime.now(timezone.utc)}})
    return {"ok": True}

# Messages
class MessageCreate(BaseModel):
    room_id: str
    persona_id: str
    content: str

@app.get("/api/messages")
def list_messages(room_id: str = Query(...), limit: int = 50, tenant_id: str = TENANT_DEFAULT):
    if db is None:
        raise HTTPException(500, "Database not configured")
    try:
        _ = ObjectId(room_id)
    except Exception:
        raise HTTPException(400, "Invalid room id")
    items = [to_str_id(m) for m in db["message"].find({"tenant_id": tenant_id, "room_id": room_id}).sort("created_at", 1).limit(limit)]
    return items

@app.post("/api/messages")
def send_message(payload: MessageCreate, tenant_id: str = TENANT_DEFAULT):
    if db is None:
        raise HTTPException(500, "Database not configured")
    now = datetime.now(timezone.utc)
    # Basic validation
    if not db["room"].find_one({"_id": ObjectId(payload.room_id), "tenant_id": tenant_id}):
        raise HTTPException(404, "Room not found")
    if not db["persona"].find_one({"_id": ObjectId(payload.persona_id), "tenant_id": tenant_id}):
        raise HTTPException(404, "Persona not found")
    doc = {
        "tenant_id": tenant_id,
        "room_id": payload.room_id,
        "persona_id": payload.persona_id,
        "content": payload.content.strip(),
        "reactions": [],
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    res = db["message"].insert_one(doc)
    return {"id": str(res.inserted_id), **doc}

# Alerts
class AlertCreate(BaseModel):
    persona_id: str
    type: str
    text: str
    radius_m: int
    lat: float
    lng: float

@app.post("/api/alerts")
def create_alert(payload: AlertCreate, tenant_id: str = TENANT_DEFAULT):
    if db is None:
        raise HTTPException(500, "Database not configured")
    if not db["persona"].find_one({"_id": ObjectId(payload.persona_id), "tenant_id": tenant_id}):
        raise HTTPException(404, "Persona not found")
    now = datetime.now(timezone.utc)
    doc = {
        "tenant_id": tenant_id,
        "persona_id": payload.persona_id,
        "type": payload.type,
        "text": payload.text.strip(),
        "radius_m": int(payload.radius_m),
        "lat": float(payload.lat),
        "lng": float(payload.lng),
        "status": "Active",
        "reactions_real": 0,
        "reactions_spam": 0,
        "reactions_helping": 0,
        "created_at": now,
        "updated_at": now,
    }
    res = db["alert"].insert_one(doc)
    return {"id": str(res.inserted_id), **doc}

@app.get("/api/alerts/nearby")
def nearby_alerts(lat: float, lng: float, radius_m: int = 1000, tenant_id: str = TENANT_DEFAULT):
    if db is None:
        raise HTTPException(500, "Database not configured")
    # For MVP with no geo index, return most recent and compute rough distance
    from math import radians, cos, sin, asin, sqrt
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return R * c
    items = []
    for a in db["alert"].find({"tenant_id": tenant_id}).sort("created_at", -1).limit(200):
        dist = haversine(lat, lng, a.get("lat", 0), a.get("lng", 0))
        if dist <= radius_m:
            doc = to_str_id(a)
            doc["distance_m"] = int(dist)
            items.append(doc)
    return items

# Simple translate/moderation placeholders
class TranslateReq(BaseModel):
    text: str
    target_lang: str = "en"

@app.post("/api/translate")
def translate(req: TranslateReq):
    # Placeholder: echo back for MVP without external key
    return {"translated": req.text, "lang": req.target_lang}

class ModerationReq(BaseModel):
    text: str

@app.post("/api/moderation")
def moderate(req: ModerationReq):
    flagged = any(bad in req.text.lower() for bad in ["hate", "suicide", "spam"])
    return {"flagged": flagged}


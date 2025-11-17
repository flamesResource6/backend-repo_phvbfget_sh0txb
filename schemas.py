"""
Database Schemas for Durarara MVP

Each Pydantic model represents a MongoDB collection. Collection name is the
lowercase of the class name (e.g., Persona -> "persona").
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# Core identity
class User(BaseModel):
    email: str
    password_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tenant_id: str = Field(default="default")
    is_banned: bool = False

class Persona(BaseModel):
    user_id: Optional[str] = None
    tenant_id: str = Field(default="default")
    handle: str = Field(..., description="Unique per tenant")
    color: str = Field("#7c3aed")
    bio: Optional[str] = None
    avatar_letter: Optional[str] = None
    trust_level: int = 1
    score_thanks: int = 0
    score_helpful: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_banned: bool = False

# Rooms & chat
class Room(BaseModel):
    tenant_id: str = Field(default="default")
    name: str
    type: Literal["global", "city", "topic", "private"] = "global"
    city: Optional[str] = None
    topic: Optional[str] = None
    invite_code: Optional[str] = None
    member_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class RoomMember(BaseModel):
    tenant_id: str = Field(default="default")
    room_id: str
    persona_id: str
    joined_at: Optional[datetime] = None

class Message(BaseModel):
    tenant_id: str = Field(default="default")
    room_id: str
    persona_id: str
    content: str
    reactions: List[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted: bool = False
    moderation_flag: Optional[str] = None

# Radius alerts
class Alert(BaseModel):
    tenant_id: str = Field(default="default")
    persona_id: str
    type: Literal["Help", "Info", "Walk Backup", "Medical", "Safety"]
    text: str
    radius_m: int = 1000
    lat: float
    lng: float
    status: Literal["Active", "Resolved"] = "Active"
    reactions_real: int = 0
    reactions_spam: int = 0
    reactions_helping: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# Safety & admin
class Reaction(BaseModel):
    tenant_id: str = Field(default="default")
    message_id: Optional[str] = None
    alert_id: Optional[str] = None
    persona_id: str
    type: Literal["pray", "bulb", "thumbs", "heart", "Real", "Spam", "Helping"]
    created_at: Optional[datetime] = None

class Report(BaseModel):
    tenant_id: str = Field(default="default")
    target_type: Literal["message", "persona", "alert"]
    target_id: str
    reporter_persona_id: str
    reason: str
    comment: Optional[str] = None
    ai_flag: Optional[str] = None
    created_at: Optional[datetime] = None

class Block(BaseModel):
    tenant_id: str = Field(default="default")
    blocker_persona_id: str
    blocked_persona_id: str
    created_at: Optional[datetime] = None

class Settings(BaseModel):
    tenant_id: str = Field(default="default")
    openai_key: Optional[str] = None
    pusher_key: Optional[str] = None
    pusher_cluster: Optional[str] = None
    message_limit_per_min: int = 60
    alert_cooldown_seconds: int = 120

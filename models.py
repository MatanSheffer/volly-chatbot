from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID

# 1. PLAYERS
class PlayerBase(BaseModel):
    name: str
    phone_number: str
    skill_level: str = "Intermediate"
    active: bool = True
    language: str = "English"
    country: str = "Israel"

class PlayerCreate(PlayerBase):
    pass

class Player(PlayerBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

# 2. GAMES
class GameBase(BaseModel):
    start_time: datetime
    location: str = "Beach Court 1"
    status: str = "recruiting"
    max_players: int = 4

class GameCreate(GameBase):
    pass

class Game(GameBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

# 3. RESPONSES
class GameResponseBase(BaseModel):
    game_id: UUID
    player_id: UUID
    status: str = "pending"
    original_message: Optional[str] = None
    ai_confidence: Optional[float] = None

class GameResponseCreate(GameResponseBase):
    pass

class GameResponse(GameResponseBase):
    id: UUID
    updated_at: datetime

    class Config:
        from_attributes = True

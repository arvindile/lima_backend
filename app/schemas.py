from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models import MatchStatus


class PlayerCreate(BaseModel):
    username: str
    password: str
    barangay_id: str
    city_id: str
    province_id: str
    avatar_url: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class PlayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    avatar_url: Optional[str]
    points: int
    barangay_id: str
    city_id: str
    province_id: str
    matches_played: int
    wins: int
    losses: int


class UsernameUpdate(BaseModel):
    new_username: str


class MatchCreate(BaseModel):
    vanguard_id: str
    sentinel_id: str
    referee_id: Optional[str] = None


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vanguard_id: str
    sentinel_id: str
    referee_id: Optional[str]
    vanguard_score: int
    sentinel_score: int
    status: MatchStatus
    total_time_seconds: int
    time_per_set_seconds: int
    winner_id: Optional[str]
    points_awarded_to_winner: Optional[int]
    points_awarded_to_loser: Optional[int]


class ScoreUpdate(BaseModel):
    vanguard_score: int
    sentinel_score: int


class MatchFinish(BaseModel):
    total_time_seconds: int
    time_per_set_seconds: int


class FriendRequestCreate(BaseModel):
    requester_id: str
    addressee_id: str


class FriendshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    requester_id: str
    addressee_id: str
    status: str


class PendingRequestOut(BaseModel):
    friendship_id: str
    requester: PlayerOut


class MessageCreate(BaseModel):
    sender_id: str
    receiver_id: str
    content: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sender_id: str
    receiver_id: str
    content: str
    sent_at: datetime

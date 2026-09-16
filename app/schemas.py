from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models import MatchStatus


class PlayerCreate(BaseModel):
    username: str
    password: str
    email: str
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


class PlayerSelfOut(PlayerOut):
    """
    PlayerOut plus the caller's own email — used ONLY for endpoints that
    return a player's own data to themselves (register, login, /auth/me,
    updating their email). Every endpoint that returns OTHER players'
    data (search, leaderboard, GET /players/{id}) uses plain PlayerOut,
    which has no email field at all, so there's no path for one player's
    email to leak to another through the API.
    """

    email: Optional[str] = None


class AuthResponse(BaseModel):
    """Returned by both POST /players (register) and POST /auth/login, so
    the app is signed in with a usable token the moment either succeeds."""

    access_token: str
    token_type: str = "bearer"
    player: PlayerSelfOut


class UsernameUpdate(BaseModel):
    new_username: str


class EmailUpdate(BaseModel):
    new_email: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


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
    vanguard_sets_won: int
    sentinel_sets_won: int
    game_started_at: Optional[datetime]
    is_paused: bool
    paused_at: Optional[datetime]
    total_paused_seconds: int
    status: MatchStatus
    total_time_seconds: int
    time_per_set_seconds: int
    winner_id: Optional[str]
    points_awarded_to_winner: Optional[int]
    points_awarded_to_loser: Optional[int]


class LiveStateUpdate(BaseModel):
    vanguard_score: int
    sentinel_score: int
    vanguard_sets_won: int
    sentinel_sets_won: int
    is_paused: bool


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


class ThreadOut(BaseModel):
    friend: PlayerOut
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None


class BlockCreate(BaseModel):
    blocked_id: str


class BlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    blocked_id: str
    blocked_username: str
    created_at: datetime


REPORT_REASONS = (
    "harassment",
    "inappropriate_content",
    "cheating",
    "spam",
    "fake_account",
    "other",
)


class ReportCreate(BaseModel):
    reported_id: str
    reason: str
    details: Optional[str] = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reporter_id: str
    reported_id: str
    reason: str
    details: Optional[str]
    status: str
    created_at: datetime

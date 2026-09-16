import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey, BigInteger, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Player(Base):
    __tablename__ = "players"

    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    points = Column(Integer, default=0, nullable=False)

    # Recovery email. Nullable because accounts created before this feature
    # existed don't have one yet — the Profile screen lets them add one.
    # New registrations require it going forward. NULL values don't collide
    # under a unique constraint (standard SQL behavior), so multiple
    # emailless legacy accounts can coexist fine.
    email = Column(String, unique=True, nullable=True, index=True)
    password_reset_code = Column(String, nullable=True)
    password_reset_expires_at = Column(DateTime, nullable=True)

    # Denormalized region fields — every leaderboard query is a flat
    # WHERE + ORDER BY + LIMIT against these, no proportional-slice
    # aggregation needed at any level.
    barangay_id = Column(String, nullable=False, index=True)
    city_id = Column(String, nullable=False, index=True)
    province_id = Column(String, nullable=False, index=True)

    username_last_changed_at = Column(DateTime, nullable=True)
    matches_played = Column(Integer, default=0, nullable=False)
    wins = Column(Integer, default=0, nullable=False)
    losses = Column(Integer, default=0, nullable=False)

    # Set by DELETE /players/me. The row itself is kept (not hard-deleted)
    # because Match rows reference players.id with no ON DELETE clause —
    # hard-deleting would break every match another player was ever part
    # of with this account. Deleting instead anonymizes the personal
    # fields in place and blocks the account from being used again; see
    # app/routers/players.py for exactly what gets scrubbed.
    is_deleted = Column(Boolean, default=False, nullable=False)

    # Set by an admin action (see app/routers/admin.py), distinct from
    # is_deleted: a ban is reversible and doesn't touch the account's data
    # or identity, it just blocks login/authenticated access until lifted.
    is_banned = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)


class MatchStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    NOT_RECORDED = "NOT_RECORDED"
    DECLINED = "DECLINED"


class Match(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True, default=_uuid)
    vanguard_id = Column(String, ForeignKey("players.id"), nullable=False)
    sentinel_id = Column(String, ForeignKey("players.id"), nullable=False)
    referee_id = Column(String, ForeignKey("players.id"), nullable=True)

    vanguard_score = Column(Integer, default=0, nullable=False)
    sentinel_score = Column(Integer, default=0, nullable=False)
    vanguard_sets_won = Column(Integer, default=0, nullable=False)
    sentinel_sets_won = Column(Integer, default=0, nullable=False)

    started_at = Column(DateTime, default=datetime.utcnow)
    # Set the moment the invite is ACCEPTED (not when it's created) — this is
    # the real "clock zero" both devices compute elapsed time from, so the
    # timer isn't polluted by however long the invite sat pending.
    game_started_at = Column(DateTime, nullable=True)
    is_paused = Column(Boolean, default=False, nullable=False)
    paused_at = Column(DateTime, nullable=True)
    total_paused_seconds = Column(Integer, default=0, nullable=False)

    ended_at = Column(DateTime, nullable=True)
    total_time_seconds = Column(BigInteger, default=0, nullable=False)
    time_per_set_seconds = Column(BigInteger, default=0, nullable=False)

    status = Column(Enum(MatchStatus, native_enum=False), default=MatchStatus.IN_PROGRESS, nullable=False)
    winner_id = Column(String, ForeignKey("players.id"), nullable=True)
    points_awarded_to_winner = Column(Integer, nullable=True)
    points_awarded_to_loser = Column(Integer, nullable=True)

    vanguard = relationship("Player", foreign_keys=[vanguard_id])
    sentinel = relationship("Player", foreign_keys=[sentinel_id])


class FriendshipStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"


class Friendship(Base):
    __tablename__ = "friendships"

    id = Column(String, primary_key=True, default=_uuid)
    requester_id = Column(String, ForeignKey("players.id"), nullable=False)
    addressee_id = Column(String, ForeignKey("players.id"), nullable=False)
    status = Column(Enum(FriendshipStatus, native_enum=False), default=FriendshipStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    sender_id = Column(String, ForeignKey("players.id"), nullable=False)
    receiver_id = Column(String, ForeignKey("players.id"), nullable=False)
    content = Column(String, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow, index=True)


class Block(Base):
    """
    One-directional: blocker_id has blocked blocked_id. Checked before
    sending a message, a friend request, or a match invite — see the
    respective routers. A brand-new table, so it's created automatically
    by Base.metadata.create_all() on next deploy; no migration script
    needed (unlike adding a column to an existing table).
    """
    __tablename__ = "blocks"

    id = Column(String, primary_key=True, default=_uuid)
    blocker_id = Column(String, ForeignKey("players.id"), nullable=False, index=True)
    blocked_id = Column(String, ForeignKey("players.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReportStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class Report(Base):
    """
    A player flagging another player's behavior for manual review.
    There's no admin UI yet — see app/routers/admin.py for the
    shared-secret-protected endpoints used to review these and act on
    them (ban/unban) until a real admin panel exists.
    """
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=_uuid)
    reporter_id = Column(String, ForeignKey("players.id"), nullable=False)
    reported_id = Column(String, ForeignKey("players.id"), nullable=False, index=True)
    reason = Column(String, nullable=False)
    details = Column(String, nullable=True)
    status = Column(Enum(ReportStatus, native_enum=False), default=ReportStatus.OPEN, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PhAddress(Base):
    """
    Reference data only — the full national province/city/barangay list
    (~39k rows), imported once via scripts/import_regions.py. Not tied to
    any player; just a lookup table the registration screen queries against.
    """
    __tablename__ = "ph_addresses"

    id = Column(String, primary_key=True, default=_uuid)
    region = Column(String, nullable=False)
    province = Column(String, nullable=False, index=True)
    city_municipality = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)
    barangay = Column(String, nullable=False)

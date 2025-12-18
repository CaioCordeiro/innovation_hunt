from __future__ import annotations

import re
import secrets
import string
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Connection, User
from app.redis_client import get_redis

CONNECT_RE = re.compile(r"^CONNECT_(?P<user_id>[A-Za-z0-9_-]{4,32})$", re.IGNORECASE)


def normalize_whatsapp_number(value: str | None) -> str:
    # Twilio provides numbers like: whatsapp:+551199999999
    return (value or "").strip()


def generate_user_id(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@dataclass(frozen=True)
class ConnectionResult:
    ok: bool
    message_to_connector: str
    message_to_connectee: str | None


def ensure_user(db: Session, phone: str) -> User:
    user = db.get(User, phone)
    if user:
        return user

    # Very small chance of collision; retry a few times.
    for _ in range(5):
        user_id = generate_user_id()
        user = User(phone_number=phone, user_id=user_id)
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            return user
        except IntegrityError:
            db.rollback()

    raise RuntimeError("Failed to allocate unique user_id")


def award_points(db: Session, *, phone: str, delta: int) -> int:
    redis = get_redis()
    redis.zincrby(settings.leaderboard_key, delta, phone)

    user = db.get(User, phone)
    if not user:
        return 0
    user.points = int(user.points) + int(delta)
    db.add(user)
    db.commit()
    return user.points


def connect_users(db: Session, *, connector_phone: str, connectee_user_id: str) -> ConnectionResult:
    connector_phone = normalize_whatsapp_number(connector_phone)
    if not connector_phone:
        return ConnectionResult(ok=False, message_to_connector="Missing WhatsApp sender.", message_to_connectee=None)

    connector = ensure_user(db, connector_phone)
    if not (connector.name and connector.email and connector.linkedin_url and connector.raw_profile_text):
        return ConnectionResult(
            ok=False,
            message_to_connector="Please register first: send 'join' and complete your profile.",
            message_to_connectee=None,
        )
    connectee = db.query(User).filter(User.user_id == connectee_user_id).one_or_none()
    if not connectee:
        return ConnectionResult(
            ok=False,
            message_to_connector="Invalid QR code (unknown user).",
            message_to_connectee=None,
        )

    if connectee.phone_number == connector.phone_number:
        return ConnectionResult(ok=False, message_to_connector="You can't connect with yourself.", message_to_connectee=None)

    conn = Connection(connector_phone=connector.phone_number, connectee_phone=connectee.phone_number)
    db.add(conn)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return ConnectionResult(
            ok=False,
            message_to_connector="Connection already recorded (no extra points).",
            message_to_connectee=None,
        )

    award_points(db, phone=connector.phone_number, delta=settings.connect_points)
    award_points(db, phone=connectee.phone_number, delta=settings.connect_points)

    a_name = connectee.name or "Someone"
    b_name = connector.name or "Someone"

    linkedin = connectee.linkedin_url or "(No LinkedIn yet)"

    msg_to_connector = (
        f"Connected with {a_name}! +{settings.connect_points} points.\n"
        f"Their LinkedIn: {linkedin}"
    )
    msg_to_connectee = f"You just connected with {b_name}! +{settings.connect_points} points."

    return ConnectionResult(ok=True, message_to_connector=msg_to_connector, message_to_connectee=msg_to_connectee)

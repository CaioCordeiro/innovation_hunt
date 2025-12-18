from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models import User
from app.redis_client import get_redis

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class OnboardingStep:
    NAME = "name"
    EMAIL = "email"
    LINKEDIN = "linkedin"
    ABOUT = "about"
    DONE = "done"


def _key(phone: str) -> str:
    return f"innovation_hunt:onboard:{phone}"


def get_step(phone: str) -> str | None:
    redis = get_redis()
    return redis.hget(_key(phone), "step")


def set_step(phone: str, step: str) -> None:
    redis = get_redis()
    redis.hset(_key(phone), mapping={"step": step})
    redis.expire(_key(phone), 60 * 60 * 24)


def clear(phone: str) -> None:
    get_redis().delete(_key(phone))


def start(db: Session, *, phone: str) -> str:
    user = db.get(User, phone)
    if user and user.name and user.email and user.linkedin_url and user.raw_profile_text:
        set_step(phone, OnboardingStep.DONE)
        return "You're already registered. Send CONNECT_<ID> from someone else's QR to play."

    if not user:
        # user record should be created by ensure_user() upstream
        pass

    set_step(phone, OnboardingStep.NAME)
    return "Welcome to Innovation Hunt! What's your *name*?"


def handle_message(db: Session, *, phone: str, text: str) -> tuple[str, bool]:
    """Returns (reply, captured_about_ready)."""
    user = db.get(User, phone)
    step_raw = get_step(phone)
    step = step_raw or OnboardingStep.NAME
    text = (text or "").strip()

    if not user:
        return ("Please send 'join' to start.", False)

    # Require explicit join to start onboarding (Twilio Sandbox constraint)
    if step_raw is None and not (user.name and user.email and user.linkedin_url and user.raw_profile_text):
        return ("Send 'join' to start registration.", False)

    if step == OnboardingStep.NAME:
        if len(text) < 2:
            return ("Please send a valid name.", False)
        user.name = text
        db.add(user)
        db.commit()
        set_step(phone, OnboardingStep.EMAIL)
        return ("Thanks! Now your *email*?", False)

    if step == OnboardingStep.EMAIL:
        if not EMAIL_RE.match(text):
            return ("That doesn't look like an email. Try again.", False)
        user.email = text
        db.add(user)
        db.commit()
        set_step(phone, OnboardingStep.LINKEDIN)
        return ("Great. Send your *LinkedIn URL*.", False)

    if step == OnboardingStep.LINKEDIN:
        if "linkedin.com" not in text.lower():
            return ("Please send a valid LinkedIn URL (must contain linkedin.com).", False)
        user.linkedin_url = text
        db.add(user)
        db.commit()
        set_step(phone, OnboardingStep.ABOUT)
        return (
            "Almost done! Paste your LinkedIn *About* section (or a short bio).\n"
            "This is used only for AI categorization.",
            False,
        )

    if step == OnboardingStep.ABOUT:
        if len(text) < 30:
            return ("Please paste a bit more (at least ~30 characters).", False)
        user.raw_profile_text = text
        db.add(user)
        db.commit()
        set_step(phone, OnboardingStep.DONE)
        clear(phone)
        return ("Registered! I'll categorize your profile shortly and send you your QR.", True)

    return ("Send 'join' to register or CONNECT_<ID> to connect.", False)

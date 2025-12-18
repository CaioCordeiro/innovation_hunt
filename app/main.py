from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from sqlalchemy.orm import Session
from twilio.twiml.messaging_response import MessagingResponse

from app.config import settings
from app.db import engine, get_db_session
from app.game import CONNECT_RE, connect_users, ensure_user, normalize_whatsapp_number
from app.models import Base, User
from app.onboarding import start as start_onboarding
from app.onboarding import handle_message
from app.hf_client import categorize_profile_text
from app.qr import generate_wa_qr_jpg, generate_wa_qr_png
from app.redis_client import get_redis
from app.twilio_utils import send_whatsapp_message, validate_twilio_signature

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("innovation_hunt")

app = FastAPI(title="Innovation Hunt")
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")


def _public_url_for(request: Request, path: str) -> str:
    """Build a public URL that Twilio can fetch (prefers forwarded headers).

    When running behind ngrok, the app sees plain http locally, but ngrok forwards
    `X-Forwarded-Proto: https` and `Host: <ngrok-domain>`.
    """
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    host = forwarded_host or request.headers.get("host")
    scheme = forwarded_proto or request.url.scheme

    if host:
        return f"{scheme}://{host}{path}"
    # Fallback to configured base URL
    return settings.public_base_url.rstrip("/") + path


@app.on_event("startup")
def _startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/media/qr/{user_id}.png")
def qr_media(user_id: str, db: Session = Depends(get_db_session)):
    user = db.query(User).filter(User.user_id == user_id).one_or_none()
    if not user or not settings.twilio_whatsapp_from:
        raise HTTPException(status_code=404, detail="Not found")

    png = generate_wa_qr_png(user_id=user.user_id, twilio_number=settings.twilio_whatsapp_from)
    return Response(content=png, media_type="image/png")


@app.get("/media/qr/{user_id}.jpg")
def qr_media_jpg(user_id: str, db: Session = Depends(get_db_session)):
    user = db.query(User).filter(User.user_id == user_id).one_or_none()
    if not user or not settings.twilio_whatsapp_from:
        raise HTTPException(status_code=404, detail="Not found")

    jpg = generate_wa_qr_jpg(user_id=user.user_id, twilio_number=settings.twilio_whatsapp_from)
    return Response(content=jpg, media_type="image/jpeg")


@app.get("/leaderboard")
def leaderboard(limit: int = 10):
    redis = get_redis()
    top = redis.zrevrange(settings.leaderboard_key, 0, max(0, limit - 1), withscores=True)
    return {
        "key": settings.leaderboard_key,
        "top": [{"phone": phone, "points": int(score)} for phone, score in top],
    }


@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db_session),
    x_twilio_signature: str | None = Header(default=None),
):
    # Twilio sends application/x-www-form-urlencoded
    form = dict(await request.form())
    from_number = normalize_whatsapp_number(form.get("From"))
    body = (form.get("Body") or "").strip()

    # Validate signature (optional)
    absolute_url = str(request.url)
    if not validate_twilio_signature(url=absolute_url, form={k: str(v) for k, v in form.items()}, signature=x_twilio_signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    ensure_user(db, from_number)

    twiml = MessagingResponse()

    # 1) CONNECT flow
    m = CONNECT_RE.match(body)
    if m:
        result = connect_users(db, connector_phone=from_number, connectee_user_id=m.group("user_id").upper())
        twiml.message(result.message_to_connector)
        if result.ok and result.message_to_connectee:
            # Proactive message to connectee (best-effort; requires Twilio creds)
            connectee = db.query(User).filter(User.user_id == m.group("user_id").upper()).one_or_none()
            if connectee:
                send_whatsapp_message(to=connectee.phone_number, body=result.message_to_connectee)
        return Response(content=str(twiml), media_type="application/xml")

    # 2) Join/onboarding trigger
    if body.lower().startswith(settings.join_keyword.lower()):
        reply = start_onboarding(db, phone=from_number)
        twiml.message(reply)
        return Response(content=str(twiml), media_type="application/xml")

    # 3) If user is mid-onboarding, capture fields
    reply, about_ready = handle_message(db, phone=from_number, text=body)

    if not about_ready:
        twiml.message(reply)
        return Response(content=str(twiml), media_type="application/xml")

    # About step completed: categorize + send QR as a single media message.
    user = db.get(User, from_number)
    category_label = "UNKNOWN"
    if user and user.raw_profile_text:
        try:
            result = categorize_profile_text(user.raw_profile_text)
            user.category = result.category
            db.add(user)
            db.commit()
            category_label = user.category or "UNKNOWN"
        except (ImportError, RuntimeError, OSError, ValueError) as e:
            logger.exception("Categorization failed: %s", e)

    if user and settings.twilio_whatsapp_from:
        qr_path = request.url_for("qr_media_jpg", user_id=user.user_id).path
        qr_url = _public_url_for(request, qr_path)
        msg = twiml.message(
            f"{reply}\n"
            f"Category: {category_label}.\n"
            f"Here is your QR code. Have others scan it to connect!"
        )
        msg.media(qr_url)
    else:
        twiml.message(reply)
        twiml.message("Set TWILIO_WHATSAPP_FROM to generate your QR.")

    return Response(content=str(twiml), media_type="application/xml")

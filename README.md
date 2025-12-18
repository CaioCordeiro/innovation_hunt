# Innovation Hunt (PoC)

WhatsApp-based gamified networking tool for CESAR at Rec’n Play.

Core flows:
- `join ...` onboarding (name/email/linkedin/about)
- QR generation (`CONNECT_<USER_ID>` deep-link)
- connection loop (anti-farming + points)
- AI categorization (LEAD/TALENT/PARTNER)
- Redis leaderboard

## Prereqs
- Python 3.10+
- Docker (for Postgres + Redis)
- Ngrok (to expose the webhook + QR media URL to Twilio)

## Quickstart (local)
1) Start Postgres + Redis:

```bash
docker compose up -d
```

2) Create env file:

```bash
cp .env.example .env
```

3) Install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4) Run API:

```bash
uvicorn app.main:app --reload --port 8000
```

5) Expose via ngrok (important: Twilio must reach both `/whatsapp` and `/media/...`):

```bash
ngrok http 8000
```

Update `PUBLIC_BASE_URL` in `.env` to your ngrok https URL.

## Twilio WhatsApp Sandbox
Configure the incoming message webhook for your Sandbox number:
- Method: `POST`
- URL: `https://<your-ngrok-domain>.ngrok-free.app/whatsapp`

Notes:
- Sandbox users must opt-in by sending `join <sandbox-keyword>` to Twilio.
- Media requires a public URL: the QR image is served from `/media/qr/{user_id}.png`.

## Environment Variables
See `.env.example`.

Minimum for onboarding + QR:
- `PUBLIC_BASE_URL`
- `TWILIO_WHATSAPP_FROM` (usually `whatsapp:+14155238886` on sandbox)

For proactive notifications (when A is notified of B connecting):
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`

For AI categorization:
- `HUGGINGFACEHUB_API_TOKEN`
- `HF_ENDPOINT_MODEL`

## Endpoints
- `POST /whatsapp` Twilio webhook (form-encoded)
- `GET /media/qr/{user_id}.png` QR image
- `GET /leaderboard?limit=10` Redis ZSET top list
- `GET /health`

## Message Commands
- `join ...` starts onboarding
- `CONNECT_<USER_ID>` connects to someone (from QR deep-link)

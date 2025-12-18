from __future__ import annotations

import io

import qrcode


def _wa_number_for_link(twilio_number: str) -> str:
    # wa.me expects digits only (no whatsapp: prefix and no +)
    return (twilio_number or "").replace("whatsapp:", "").replace("+", "").strip()


def generate_wa_qr_png(*, user_id: str, twilio_number: str) -> bytes:
    number = _wa_number_for_link(twilio_number)
    link = f"https://wa.me/{number}?text=CONNECT_{user_id}"

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def generate_wa_qr_jpg(*, user_id: str, twilio_number: str) -> bytes:
    """JPEG is often the safest option for WhatsApp media delivery."""
    number = _wa_number_for_link(twilio_number)
    link = f"https://wa.me/{number}?text=CONNECT_{user_id}"

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()

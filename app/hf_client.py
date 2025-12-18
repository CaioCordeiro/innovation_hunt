from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from app.config import settings


@dataclass(frozen=True)
class CategorizationResult:
    category: str
    reasoning: str | None = None


def _strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        # remove leading ```lang
        t = t.split("\n", 1)[1] if "\n" in t else ""
        # remove trailing ```
        if "```" in t:
            t = t.rsplit("```", 1)[0]
    return t.strip()


@lru_cache(maxsize=1)
def _chat():
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

    if not settings.hf_token:
        raise RuntimeError("HUGGINGFACEHUB_API_TOKEN is not set")

    llm = HuggingFaceEndpoint(
        repo_id=settings.hf_endpoint_model,
        huggingfacehub_api_token=settings.hf_token,
        temperature=settings.hf_temperature,
        max_new_tokens=settings.hf_max_new_tokens,
    )
    return ChatHuggingFace(llm=llm)


def categorize_profile_text(profile_text: str) -> CategorizationResult:
    """Categorize as LEAD/TALENT/PARTNER using hosted Hugging Face inference.

    Returns JSON-only output from the model, parsed locally.
    """
    text = (profile_text or "").strip()
    if not text:
        return CategorizationResult(category="PARTNER", reasoning="Empty profile text")

    from langchain_core.messages import HumanMessage, SystemMessage

    system = (
        "You categorize CESAR event participants. "
        "Return ONLY valid JSON (no markdown) with keys: category, reasoning. "
        "category must be one of: LEAD, TALENT, PARTNER."
    )
    human = (
        "Given this profile text, categorize the person as: "
        "LEAD (decision maker), TALENT (dev/designer/manager), or PARTNER (other tech entities).\n\n"
        f"PROFILE:\n{text}"
    )

    try:
        chat = _chat()
        resp = chat.invoke([SystemMessage(content=system), HumanMessage(content=human)])
        raw = getattr(resp, "content", "") or ""
    except (ImportError, RuntimeError, OSError, ValueError) as e:
        return CategorizationResult(category="PARTNER", reasoning=f"HF endpoint failed: {type(e).__name__}")

    raw = _strip_code_fences(str(raw))
    try:
        data = json.loads(raw)
        category = str(data.get("category", "PARTNER")).upper().strip()
        reasoning = data.get("reasoning")
    except (json.JSONDecodeError, TypeError, ValueError):
        category = "PARTNER"
        reasoning = (raw[:500] if raw else "Unparseable model output")

    if category not in {"LEAD", "TALENT", "PARTNER"}:
        category = "PARTNER"
    return CategorizationResult(category=category, reasoning=str(reasoning)[:500] if reasoning else None)

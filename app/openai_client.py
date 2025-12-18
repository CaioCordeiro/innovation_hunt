"""Deprecated: OpenAI categorization.

This PoC now uses Hugging Face hosted inference (HuggingFaceEndpoint + ChatHuggingFace).
This module is kept only for backward compatibility.
"""

from __future__ import annotations

from app import hf_client as _hf

CategorizationResult = _hf.CategorizationResult


def categorize_profile_text(profile_text: str) -> CategorizationResult:
    return _hf.categorize_profile_text(profile_text)

"""Tiny Spanish/English detector for user queries (RF-01, HU-04); no dependencies.

Counts common function words of each language; Spanish-only characters (ñ, ¿, ¡,
accented vowels) add weight. Ties and empty texts default to Spanish, the main language
of the bank's staff (RNF-12).
"""

from __future__ import annotations

import re

from src.prompts import Language

# fmt: off
_ES_WORDS = frozenset((
    "el", "la", "los", "las", "un", "una", "unos", "unas", "mi", "mis", "tu", "su", "es",
    "son", "no", "se", "de", "del", "al", "que", "como", "por", "para", "con", "sin", "y",
    "o", "en", "me", "te", "le", "lo", "puedo", "puede", "tengo", "tiene", "hay", "esta",
    "estoy", "funciona", "sirve", "ayuda", "ayudame", "necesito", "quiero", "cuando",
    "donde", "porque", "pero", "muy", "ya", "otra", "otro", "sale",
))
_EN_WORDS = frozenset((
    "the", "an", "my", "your", "his", "her", "is", "are", "was", "not", "does", "doesn't",
    "don't", "can't", "cannot", "won't", "isn't", "i", "i'm", "it", "it's", "this", "that",
    "how", "what", "why", "when", "where", "to", "of", "for", "with", "and", "or", "on",
    "in", "at", "from", "can", "do", "have", "has", "need", "want", "please", "help",
    "work", "working", "keeps", "get", "got",
))
# fmt: on
_ES_CHARS = re.compile(r"[ñáéíóúü¿¡]")
_WORD = re.compile(r"[a-zñáéíóúü']+")


def detect_language(text: str) -> Language:
    """``"es"`` or ``"en"`` for a short user message."""
    lowered = text.lower()
    words = _WORD.findall(lowered)
    spanish = sum(word in _ES_WORDS for word in words) + 2 * len(_ES_CHARS.findall(lowered))
    english = sum(word in _EN_WORDS for word in words)
    return "en" if english > spanish else "es"

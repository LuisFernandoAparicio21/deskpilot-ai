"""Detection and redaction of sensitive data in free text (RN-05, RNF-05).

Passwords, PINs (NIP), tokens or keys, card numbers and CURP must never be stored or
logged. ``contains_sensitive`` reports which kinds appear in a text and ``redact``
replaces each occurrence with ``[REDACTED:<kind>]``. The structured logger and
``crear_ticket`` (T17) both reuse these functions.

Detection is pattern based and deliberately conservative to avoid false positives on
normal service-desk text: a password is only detected after an explicit separator
("es", "is", ":" or "="), a PIN must be 4-8 digits, a card number must have 13-19 digits
and pass the Luhn check, and a generic token must mix upper case, lower case and digits.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

PASSWORD = "password"
PIN = "pin"
TOKEN = "token"
CARD = "card"
CURP = "curp"

_NOT_REDACTED = r"(?!\[REDACTED)"

# "mi contraseña es X", "password: X", "my new password is X", "clave de acceso: X".
_PASSWORD_RE = re.compile(
    r"\b(?:contrase[ñn]a|password|passwd|pwd|clave\s+(?:de\s+acceso|secreta|din[áa]mica))"
    r"(?:\s+(?:actual|nueva|anterior|temporal|vieja|new|old|current|temporary))?"
    r"(?:\s*[:=]\s*|\s+(?:es|is|era|was)\s+)"
    rf"{_NOT_REDACTED}(?P<value>[^\s,;]+)",
    re.IGNORECASE,
)

# "NIP 1234", "el nip es 987654", "PIN: 4321".
_PIN_RE = re.compile(
    r"\b(?:nip|pin)(?:\s*[:=]\s*|\s+(?:es|is)\s+|\s+)(?P<value>\d{4,8})(?!\d)",
    re.IGNORECASE,
)

# "token: X", "api_key=X", "secret: X".
_TOKEN_LABEL_RE = re.compile(
    r"\b(?:token|api[_ -]?key|secret|secreto|access[_ -]?key)\s*[:=]\s*"
    rf"{_NOT_REDACTED}(?P<value>[^\s,;]+)",
    re.IGNORECASE,
)

# Well-known secret shapes (provider keys, GitHub/AWS/Slack tokens, JWT, bearer tokens).
_TOKEN_SHAPE_RE = re.compile(
    r"(?P<value>"
    r"\bsk-[A-Za-z0-9_\-]{16,}"
    r"|\bgh[pousr]_[A-Za-z0-9]{30,}"
    r"|\bgithub_pat_[A-Za-z0-9_]{30,}"
    r"|\bAKIA[0-9A-Z]{16}\b"
    r"|\bAIza[0-9A-Za-z_\-]{35}"
    r"|\bxox[abprs]-[A-Za-z0-9\-]{10,}"
    r"|\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"
    r")"
    r"|(?<=Bearer )(?P<bearer>[A-Za-z0-9._~+/\-]{16,}=*)",
)

# Long opaque strings (32+ chars) are treated as secrets only if they mix classes.
_OPAQUE_RE = re.compile(r"(?<![A-Za-z0-9_\-])[A-Za-z0-9_\-]{32,}(?![A-Za-z0-9_\-])")

# 13-19 digits, optionally grouped with spaces or dashes; validated with Luhn afterwards.
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ \-]?){12,18}\d(?!\d)")

# CURP: 18 characters (initials, birth date, sex, state, inner consonants, homoclave and
# check digit). Structure from the RENAPO instructivo; state codes as in python-stdnum.
_CURP_STATES = (
    "AS|BC|BS|CC|CH|CL|CM|CS|DF|DG|GR|GT|HG|JC|MC|MN|MS|"
    "NE|NL|NT|OC|PL|QR|QT|SL|SP|SR|TC|TL|TS|VZ|YN|ZS"
)
_CURP_RE = re.compile(
    r"\b[A-Z][AEIOUX][A-Z]{2}\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[HMX]"
    rf"(?:{_CURP_STATES})[B-DF-HJ-NP-TV-Z]{{3}}[0-9A-Z]\d\b",
    re.IGNORECASE,
)


def luhn_is_valid(digits: str) -> bool:
    """Return True if ``digits`` (only 0-9) passes the Luhn checksum."""
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _placeholder(kind: str) -> str:
    return f"[REDACTED:{kind}]"


def _replace_group(kind: str) -> Callable[[re.Match[str]], str]:
    """Replace only the named ``value`` group (or ``bearer``), keeping the label."""

    def _sub(match: re.Match[str]) -> str:
        group = "value" if match.group("value") is not None else "bearer"
        start, end = match.span(group)
        offset = match.start()
        whole = match.group(0)
        return whole[: start - offset] + _placeholder(kind) + whole[end - offset :]

    return _sub


def _replace_opaque(match: re.Match[str]) -> str:
    value = match.group(0)
    mixed = (
        any(c.isupper() for c in value)
        and any(c.islower() for c in value)
        and any(c.isdigit() for c in value)
    )
    return _placeholder(TOKEN) if mixed else value


def _replace_card(match: re.Match[str]) -> str:
    digits = re.sub(r"[ \-]", "", match.group(0))
    if 13 <= len(digits) <= 19 and luhn_is_valid(digits):
        return _placeholder(CARD)
    return match.group(0)


@dataclass(frozen=True)
class _Rule:
    kind: str
    pattern: re.Pattern[str]
    replace: Callable[[re.Match[str]], str]


# Order matters: labelled values first, so "password: sk-..." counts as a password.
_RULES: tuple[_Rule, ...] = (
    _Rule(PASSWORD, _PASSWORD_RE, _replace_group(PASSWORD)),
    _Rule(PIN, _PIN_RE, _replace_group(PIN)),
    _Rule(TOKEN, _TOKEN_LABEL_RE, _replace_group(TOKEN)),
    _Rule(TOKEN, _TOKEN_SHAPE_RE, _replace_group(TOKEN)),
    _Rule(TOKEN, _OPAQUE_RE, _replace_opaque),
    _Rule(CARD, _CARD_RE, _replace_card),
    _Rule(CURP, _CURP_RE, lambda _match: _placeholder(CURP)),
)


def _scan(text: str) -> tuple[str, list[str]]:
    """Apply every rule in order; return the redacted text and the kinds found."""
    found: set[str] = set()
    for rule in _RULES:
        new_text = rule.pattern.sub(rule.replace, text)
        if new_text != text:
            found.add(rule.kind)
            text = new_text
    return text, sorted(found)


def contains_sensitive(text: str) -> list[str]:
    """Return the sorted kinds of sensitive data found in ``text`` (empty if none)."""
    return _scan(text)[1]


def redact(text: str) -> str:
    """Return ``text`` with every sensitive value replaced by ``[REDACTED:<kind>]``."""
    return _scan(text)[0]


def sensitive_values(text: str) -> list[str]:
    """Return the literal sensitive values ``redact`` would replace in ``text``.

    Meant for checks such as the evaluation's "the secret never leaks"; callers must
    never log or store the result.
    """
    values: list[str] = []
    for rule in _RULES:

        def _record(match: re.Match[str], rule: _Rule = rule) -> str:
            replacement = rule.replace(match)
            if replacement != match.group(0):
                named = [match.group(g) for g in ("value", "bearer") if g in match.re.groupindex]
                values.append(next((v for v in named if v is not None), match.group(0)))
            return replacement

        text = rule.pattern.sub(_record, text)
    return values

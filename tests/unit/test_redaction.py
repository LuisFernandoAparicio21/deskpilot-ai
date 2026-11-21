"""Unit tests for sensitive-data detection and redaction (RN-05, RNF-05)."""

from __future__ import annotations

import pytest

from src.utils.redaction import (
    CARD,
    CURP,
    PASSWORD,
    PIN,
    TOKEN,
    contains_sensitive,
    luhn_is_valid,
    redact,
)

# All values below are synthetic: test card numbers, invented CURPs and fake tokens.
VALID_CARD = "4111 1111 1111 1111"  # Visa test number, passes Luhn.
NON_LUHN_16_DIGITS = "4111111111111112"  # 16 digits that fail Luhn.
SYNTHETIC_CURP = "BEML920313HMCLNS09"


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        ("4111111111111111", True),
        ("5555555555554444", True),
        ("378282246310005", True),
        ("4111111111111112", False),
        ("1234567890123456", False),
    ],
)
def test_luhn_is_valid(number: str, expected: bool) -> None:
    assert luhn_is_valid(number) is expected


@pytest.mark.parametrize(
    ("text", "secret", "kind"),
    [
        ("Hola, mi contraseña es Altiplano#2024 y no entra", "Altiplano#2024", PASSWORD),
        ("password: S3cr3t!pass", "S3cr3t!pass", PASSWORD),
        ("Mi contrasena actual es hunter22", "hunter22", PASSWORD),
        ("my password is qwerty123", "qwerty123", PASSWORD),
        ("clave de acceso: Zx81!kq", "Zx81!kq", PASSWORD),
        ("Mi NIP 1234 ya no funciona", "1234", PIN),
        ("el nip es 987654", "987654", PIN),
        ("PIN: 4321", "4321", PIN),
        (f"Mi tarjeta {VALID_CARD} está bloqueada", VALID_CARD, CARD),
        ("tarjeta 5555-5555-5555-4444", "5555-5555-5555-4444", CARD),
        (f"Mi CURP es {SYNTHETIC_CURP}", SYNTHETIC_CURP, CURP),
        (f"curp {SYNTHETIC_CURP.lower()}", SYNTHETIC_CURP.lower(), CURP),
        ("token: abc123def456ghi789", "abc123def456ghi789", TOKEN),
        ("api_key=zzzz-yyyy-xxxx-0000", "zzzz-yyyy-xxxx-0000", TOKEN),
        ("usa sk-ant-api03-AbCdEfGhIjKlMnOpQrStUv", "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUv", TOKEN),
        ("ghp_" + "a1B2" * 9 + " filtrado", "ghp_" + "a1B2" * 9, TOKEN),
        ("AKIAABCDEFGHIJKLMNOP es la llave", "AKIAABCDEFGHIJKLMNOP", TOKEN),
        ("Authorization: Bearer abcDEF123456ghiJKL789", "abcDEF123456ghiJKL789", TOKEN),
        ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl", "eyJhbGciOiJIUzI1NiJ9", TOKEN),
        ("llave Xy7_kP2qLm9vRt4wZs8bNc3dFg6hJk1a ok", "Xy7_kP2qLm9vRt4wZs8bNc3dFg6hJk1a", TOKEN),
    ],
)
def test_positive_cases_are_detected_and_redacted(text: str, secret: str, kind: str) -> None:
    assert kind in contains_sensitive(text)
    redacted = redact(text)
    assert secret not in redacted
    assert f"[REDACTED:{kind}]" in redacted


@pytest.mark.parametrize(
    "text",
    [
        "No puedo entrar a mi correo, olvidé mi contraseña",
        "La contraseña no funciona desde ayer",
        "Necesito restablecer el NIP de mi tarjeta",
        "El ticket TCK-000123 sigue abierto desde el 2024-05-01",
        "Llamar al 5512345678 en horario de oficina",
        NON_LUHN_16_DIGITS,
        f"Referencia {NON_LUHN_16_DIGITS} del pago",
        "12345678901234567890",  # 20 digits: outside the 13-19 card range
        "BEML920313HMCLNS0",  # 17 characters: not a CURP
        "request 0123456789abcdef0123456789abcdef procesado",  # uuid hex: lowercase only
        "La impresora del piso 3 no imprime",
        "",
    ],
)
def test_negative_cases_are_left_untouched(text: str) -> None:
    assert contains_sensitive(text) == []
    assert redact(text) == text


def test_non_luhn_sixteen_digits_is_not_redacted() -> None:
    text = f"Número {NON_LUHN_16_DIGITS}"
    assert redact(text) == text


def test_multiple_types_are_reported_once_and_sorted() -> None:
    text = (
        f"password: abc12345, NIP 4321, tarjeta {VALID_CARD}, "
        f"CURP {SYNTHETIC_CURP}, otra tarjeta 5555555555554444"
    )
    assert contains_sensitive(text) == sorted({PASSWORD, PIN, CARD, CURP})
    redacted = redact(text)
    for secret in ("abc12345", "4321", VALID_CARD, SYNTHETIC_CURP, "5555555555554444"):
        assert secret not in redacted


def test_password_value_that_looks_like_token_is_reported_as_password_only() -> None:
    text = "password: sk-ant-api03-AbCdEfGhIjKlMnOpQrStUv"
    assert contains_sensitive(text) == [PASSWORD]
    assert redact(text) == "password: [REDACTED:password]"


def test_redact_is_idempotent() -> None:
    once = redact(f"mi contraseña es Secreta123 y mi tarjeta {VALID_CARD}")
    assert redact(once) == once
    assert contains_sensitive(once) == []

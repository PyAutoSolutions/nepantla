"""Modelos de entrada (Pydantic) y constantes compartidas.

Todos los modelos usan `extra="forbid"`: si alguien manda un campo que no
está en la lista, la petición se rechaza completa. Es una defensa de
privacidad, no solo de limpieza: impide que un cliente mal hecho "cuele"
datos de pacientes en un endpoint que no los espera.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ID_PATTERN = r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$"

USAGE_EVENTS = (
    "pack_downloaded",
    "scenario_opened",
    "summary_generated",
    "interpreter_requested",
)

# Motivos cerrados para reportar un audio. No hay texto libre a propósito:
# un campo abierto es el lugar donde terminan escribiéndose datos de pacientes.
REPORT_REASONS = (
    "wrong_meaning",   # dice otra cosa
    "wrong_variant",   # es de otra variante o no se entiende aquí
    "bad_audio",       # se oye mal, cortado o con ruido
    "offensive",       # resulta ofensivo o inapropiado
    "other",           # otro problema
)

ANSWER_TYPES = ("yes_no", "pictogram", "body_map", "pain_scale", "duration", "none")
PACK_STATUSES = ("draft", "approved", "withdrawn")
SESSION_ROLES = ("speaker", "reviewer", "guardian")

Ident = Annotated[str, StringConstraints(pattern=ID_PATTERN)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Token = Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=200)]


def _no_control_chars(value: str) -> str:
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("No se permiten caracteres de control.")
    return value


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UsageIn(Strict):
    """Lo único que acepta /api/usage."""

    pack_id: Ident
    event: Literal[USAGE_EVENTS]  # type: ignore[valid-type]
    n: int = Field(default=1, ge=1, le=500)


class ReportIn(Strict):
    pack_id: Ident
    phrase_id: Ident
    reason: Literal[REPORT_REASONS]  # type: ignore[valid-type]


class ReportUpdate(Strict):
    status: Literal["resolved", "dismissed", "open"]


class PackCreate(Strict):
    pack_id: Ident
    language: ShortText
    variant: ShortText
    community: OptionalText = ""
    license: OptionalText = ""
    community_label: Optional[OptionalText] = None
    guardians: list[ShortText] = Field(default_factory=list, max_length=12)

    _clean = field_validator("language", "variant", "community", "license")(_no_control_chars)


class PackUpdate(Strict):
    community: Optional[OptionalText] = None
    license: Optional[OptionalText] = None
    community_label: Optional[OptionalText] = None
    guardians: Optional[list[ShortText]] = Field(default=None, max_length=12)


class SessionCreate(Strict):
    pack_id: Ident
    role: Literal[SESSION_ROLES]  # type: ignore[valid-type]
    alias: ShortText
    is_interpreter: bool = False
    days: int = Field(default=30, ge=1, le=180)

    _clean = field_validator("alias")(_no_control_chars)


class ConsentIn(Strict):
    """Cada casilla del consentimiento se acepta por separado."""

    credit_name: ShortText
    understands_use: Literal[True]
    understands_withdrawal: Literal[True]
    accepts_license: Literal[True]
    is_adult: Literal[True]

    _clean = field_validator("credit_name")(_no_control_chars)


class ReviewIn(Strict):
    recording_id: int = Field(ge=1)
    verdict: Literal["approve", "reject"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] = ""


class WithdrawIn(Strict):
    token: Token
    scope: Literal["voice", "phrase", "pack"] = "voice"
    phrase_id: Optional[Ident] = None
    dry_run: bool = False

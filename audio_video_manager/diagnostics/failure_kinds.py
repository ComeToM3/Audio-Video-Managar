"""Classification des échecs archive + messages FR (détails techniques séparés)."""

from __future__ import annotations

from enum import Enum


class FailureKind(str, Enum):
    EXTRACTION = "extraction"
    INTEGRITY = "integrity"
    METADATA = "metadata"
    PUBLISH = "publish"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    UNKNOWN = "unknown"


def freac_signed_code(returncode: int | None) -> int | None:
    """Normalise les codes unsigned Windows (ex. 4294967293 → -3)."""
    if returncode is None:
        return None
    if returncode > 0x7FFFFFFF:
        return returncode - (1 << 32)
    return returncode


def classify_freac_returncode(returncode: int | None) -> FailureKind:
    return FailureKind.EXTRACTION


_FREAC_HINTS: dict[int, str] = {
    -1: "fre:ac signale une erreur générique ou une conversion interrompue.",
    -2: "Option ou piste fre:ac invalide (vérifiez lecteur et paramètres).",
    -3: "fre:ac n’a pas trouvé un fichier attendu (souvent un argument mal formé).",
    -4: "Extraction CD désactivée côté fre:ac.",
}


def format_user_error(
    *,
    kind: FailureKind,
    summary: str,
    technical: str | None = None,
    action: str | None = None,
) -> str:
    """Message FR lisible ; le détail technique reste optionnel et distinct."""
    lines = [summary]
    if action:
        lines.append(f"Action possible : {action}")
    if technical:
        lines.append(f"Détail technique : {technical}")
    return "\n".join(lines)


def freac_user_message(
    returncode: int | None,
    *,
    flac_count: int = 0,
    stderr_tail: str = "",
) -> tuple[str, str]:
    """
    Retourne (résumé FR, détail technique).

    Ne masque jamais le code ; n’assouplit pas la règle returncode == 0.
    """
    signed = freac_signed_code(returncode)
    tech = f"freaccmd returncode={returncode}"
    if signed is not None and signed != returncode:
        tech += f" (signé {signed})"
    hint = _FREAC_HINTS.get(signed or 0, "fre:ac a renvoyé un code d’erreur.")
    summary = f"L’extraction audio a échoué. {hint}"
    if flac_count:
        summary += (
            f" {flac_count} fichier(s) FLAC sont déjà présents dans le dossier "
            "temporaire du job (récupérables, non publiés automatiquement)."
        )
    if stderr_tail.strip():
        tech += f" | stderr: {stderr_tail.strip()[:400]}"
    action = (
        "Ne relancez pas sans consignes si des FLAC existent déjà ; "
        "consultez freac_stdout.txt / freac_stderr.txt dans le dossier du job."
        if flac_count
        else "Vérifiez le CD, le lecteur et les journaux fre:ac du job."
    )
    return format_user_error(
        kind=FailureKind.EXTRACTION,
        summary=summary,
        technical=tech,
        action=action,
    ), tech

from __future__ import annotations

from pathlib import Path

def setup_prompt() -> str:
    candidates = [
        Path(__file__).resolve().parent / "setup_prompt.md",
        Path(__file__).resolve().parents[2] / "prompts" / "garden-setup.md",
    ]
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError("garden setup prompt is missing")


def estimate_frost_mmdd(latitude: float) -> tuple[str, str]:
    """Rough average frost dates from latitude. Northern hemisphere."""
    lat = abs(float(latitude))
    if lat < 28:
        return "02-15", "12-01"
    if lat < 32:
        return "03-10", "11-20"
    if lat < 36:
        return "03-25", "11-10"
    if lat < 40:
        return "04-15", "10-20"
    if lat < 44:
        return "05-05", "10-05"
    return "05-25", "09-20"

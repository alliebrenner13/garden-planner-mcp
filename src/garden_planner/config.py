from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path


def project_root() -> Path:
    env = os.environ.get("GARDEN_PLANNER_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def config_path() -> Path:
    env = os.environ.get("GARDEN_PLANNER_CONFIG")
    if env:
        return Path(env)
    return project_root() / "config.toml"


def db_path() -> Path:
    env = os.environ.get("GARDEN_PLANNER_DB")
    if env:
        return Path(env)
    return project_root() / "data" / "garden.db"


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float
    timezone: str


@dataclass(frozen=True)
class FrostClimate:
    last_spring: str
    first_fall: str
    threshold_c: float


@dataclass(frozen=True)
class PlotNotes:
    name: str
    aspect: str
    sun: str
    mulch: str
    rules: str


@dataclass(frozen=True)
class AppConfig:
    location: Location
    frost: FrostClimate
    plot: PlotNotes

    def last_spring_date(self, year: int) -> date:
        return _mmdd_to_date(self.frost.last_spring, year)

    def first_fall_date(self, year: int) -> date:
        return _mmdd_to_date(self.frost.first_fall, year)


def _mmdd_to_date(mmdd: str, year: int) -> date:
    month, day = (int(part) for part in mmdd.split("-", 1))
    return date(year, month, day)


def config_exists(path: Path | None = None) -> bool:
    return (path or config_path()).is_file()


class ConfigMissingError(FileNotFoundError):
    """Raised when the gardener has not finished first-run setup."""


def load_config(path: Path | None = None) -> AppConfig:
    path = path or config_path()
    if not path.is_file():
        raise ConfigMissingError(
            f"No garden config at {path}. Run first-run setup or copy config.example.toml to config.toml."
        )
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    loc = raw["location"]
    frost = raw["frost"]
    plot = raw.get("garden") or {}
    return AppConfig(
        location=Location(
            latitude=float(loc["latitude"]),
            longitude=float(loc["longitude"]),
            timezone=str(loc["timezone"]),
        ),
        frost=FrostClimate(
            last_spring=str(frost["last_spring"]),
            first_fall=str(frost["first_fall"]),
            threshold_c=float(frost["threshold_c"]),
        ),
        plot=PlotNotes(
            name=str(plot.get("name") or "Garden"),
            aspect=str(plot.get("aspect") or ""),
            sun=str(plot.get("sun") or ""),
            mulch=str(plot.get("mulch") or ""),
            rules=str(plot.get("rules") or ""),
        ),
    )


def _toml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def save_config(cfg: AppConfig, path: Path | None = None) -> None:
    path = path or config_path()
    text = (
        "[location]\n"
        f"latitude = {cfg.location.latitude}\n"
        f"longitude = {cfg.location.longitude}\n"
        f"timezone = {_toml_str(cfg.location.timezone)}\n"
        "\n"
        "[frost]\n"
        f"last_spring = {_toml_str(cfg.frost.last_spring)}\n"
        f"first_fall = {_toml_str(cfg.frost.first_fall)}\n"
        f"threshold_c = {cfg.frost.threshold_c}\n"
        "\n"
        "[garden]\n"
        f"name = {_toml_str(cfg.plot.name)}\n"
        f"aspect = {_toml_str(cfg.plot.aspect)}\n"
        f"sun = {_toml_str(cfg.plot.sun)}\n"
    )
    path.write_text(text, encoding="utf-8")

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

SourceStatus = Literal["active", "planned", "disabled"]


@dataclass(frozen=True)
class SourceProfile:
    id: str
    name: str
    status: SourceStatus
    adapter: str
    homepage_url: str
    description: str
    schema_version: str | None = None
    domains: tuple[str, ...] = field(default_factory=tuple)

    def connection_url(self) -> str | None:
        if self.status != "active":
            return None
        env_key = f"{self.id.upper()}_DB_URL"
        url = os.environ.get(env_key, "").strip()
        if url:
            return url
        if self.id == "iea":
            url = os.environ.get("IEA_DB_URL", "").strip()
            if url:
                return url
            host = os.environ.get("PGHOST", "localhost")
            port = os.environ.get("PGPORT", "5432")
            database = os.environ.get("PGDATABASE", "iea_data")
            user = os.environ.get("PGUSER", "postgres")
            password = os.environ.get("PGPASSWORD", "postgres")
            return f"postgresql://{user}:{password}@{host}:{port}/{database}"
        return None


class SourceRegistry:
    def __init__(self, profiles: dict[str, SourceProfile]) -> None:
        self._profiles = profiles

    @classmethod
    def load(cls, config_path: str | Path) -> SourceRegistry:
        path = Path(config_path)
        if not path.is_file():
            raise FileNotFoundError(f"Sources config not found: {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        profiles: dict[str, SourceProfile] = {}
        for item in raw.get("sources", []):
            profile = SourceProfile(
                id=str(item["id"]),
                name=str(item["name"]),
                status=item.get("status", "planned"),
                adapter=str(item.get("adapter", "generic")),
                homepage_url=str(item.get("homepage_url", "")),
                description=str(item.get("description", "")).strip(),
                schema_version=item.get("schema_version"),
                domains=tuple(item.get("domains") or []),
            )
            profiles[profile.id] = profile
        return cls(profiles)

    def list_profiles(self) -> list[SourceProfile]:
        return list(self._profiles.values())

    def get(self, source_id: str) -> SourceProfile | None:
        return self._profiles.get(source_id)

    def require(self, source_id: str) -> SourceProfile:
        profile = self.get(source_id)
        if profile is None:
            raise KeyError(f"Unknown source: {source_id}")
        return profile


_registry: SourceRegistry | None = None


def get_registry() -> SourceRegistry:
    global _registry
    if _registry is None:
        candidates = [
            os.environ.get("SOURCES_CONFIG", "").strip(),
            "config/sources.yaml",
        ]
        repo_root = Path(__file__).resolve().parents[3]
        candidates.append(str(repo_root / "config" / "sources.yaml"))

        config = next((path for path in candidates if path and Path(path).is_file()), "")
        if not config:
            raise FileNotFoundError(
                "Sources config not found. Set SOURCES_CONFIG or place config/sources.yaml in project root."
            )
        _registry = SourceRegistry.load(config)
    return _registry

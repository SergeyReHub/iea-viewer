from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "iea-viewer-v2-api"
    app_env: str = "dev"
    api_port: int = 8015

    pghost: str = "host.docker.internal"
    pgport: int = 5442
    pgdatabase: str = "parsers_eurostat"
    pguser: str = "parsers"
    pgpassword: str = "parsers"
    iea_db_url: str = ""

    sources_config: str = "config/sources.yaml"

    cors_origins: str = "*"

    audit_viewer_ips: str = ""
    identity_ip_map_extra: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

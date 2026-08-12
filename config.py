import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: Union[List[int], str] = []
    DB_URL: str = "sqlite+aiosqlite:///expenses.db"
    DEFAULT_REMINDER_TIME: str = "21:00"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            # Split comma separated
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        elif isinstance(v, int):
            return [v]
        return v

    def is_admin(self, user_id: int) -> bool:
        if isinstance(self.ADMIN_IDS, list):
            return user_id in self.ADMIN_IDS
        return False


settings = Settings()

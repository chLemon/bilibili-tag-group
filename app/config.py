from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./my_bilibili.db"
    sync_interval_minutes: int = 60


settings = Settings()

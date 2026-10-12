import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "VyaparFlow AI"
    API_V1_STR: str = "/api"
    DEMO_MODE: bool = False
    OPENAI_API_KEY: str = "" # Or any other provider
    GEMINI_API_KEY: str = ""
    VISION_PROVIDER: str = "gemini"
    GEMINI_VISION_MODEL: str = "gemini-3.5-flash-lite"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

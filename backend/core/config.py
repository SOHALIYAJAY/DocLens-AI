# core/config.py
# This file holds the main configuration for the FastAPI application.

class Settings:
    PROJECT_NAME: str = "AI PDF Assistant API"
    PROJECT_VERSION: str = "1.0.0"
    API_PREFIX: str = ""

# Instantiate the settings so it can be imported across the project
settings = Settings()

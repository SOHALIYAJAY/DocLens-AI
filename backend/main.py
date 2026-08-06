# main.py
# This is the entry point of the FastAPI application.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from api.endpoints import router as api_router
from api.image import router as image_router

# 1. Initialize the FastAPI app with settings
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION
)

# 2. Configure CORS (Cross-Origin Resource Sharing)
# This is CRITICAL for Chrome Extensions. It allows your extension's frontend
# (which runs on a completely different "origin" like chrome-extension://...)
# to make network requests to this backend without being blocked by the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (change this to your extension ID in production)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# 3. Include the API router
app.include_router(api_router)
app.include_router(image_router)

# 4. A simple root endpoint to check if the server is running
@app.get("/")
async def root():
    return {"message": "AI PDF Assistant API is running. Check /docs for documentation."}

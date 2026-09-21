from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(
    title="CiteGuard API",
    description="Backend API for Citation Verification and Evidence Alignment",
    version="1.0.0"
)

# Configure CORS for the frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For MVP, allow all. Restrict in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the main API routes
app.include_router(router, prefix="/api")

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "CiteGuard Backend"}

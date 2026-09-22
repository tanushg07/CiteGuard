from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.api.routes import router

app = FastAPI(
    title="CiteGuard API",
    description="AI-Powered Citation Verification & Evidence Alignment Platform",
    version="2.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include main API routes
app.include_router(router, prefix="/api")

@app.get("/api")
def root():
    return {
        "service": "CiteGuard API",
        "version": "2.0.0",
        "status": "operational",
        "endpoints": {
            "verify_pdf": "POST /api/verify",
            "analyze_text": "POST /api/analyze-text",
            "benchmark": "GET /api/benchmark",
            "results": "GET /api/results/{job_id}",
            "export": "GET /api/export/{job_id}?format=json|csv"
        }
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "CiteGuard Backend"}


frontend = Path(__file__).resolve().parents[1] / 'citeguard-frontend' / 'dist'
if frontend.is_dir():
    app.mount('/', StaticFiles(directory=frontend, html=True), name='frontend')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.api.endpoints import router as workflow_router
from app.api.eval import router as eval_router
from app.core.database import engine, Base, ensure_workflow_columns
import app.models.workflow # Ensure models are loaded

# Create tables
Base.metadata.create_all(bind=engine)
ensure_workflow_columns()

app = FastAPI(title="VyaparFlow AI API")

Path("uploads").mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For demo purposes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflow_router, prefix="/api")
app.include_router(eval_router, prefix="/api/evaluation")


@app.get("/")
def read_root():
    return {"message": "Welcome to VyaparFlow AI API"}

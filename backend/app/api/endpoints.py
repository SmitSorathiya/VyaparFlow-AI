from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
import os

from app.core.database import get_db
from app.models.workflow import Workflow, AuditLog
from app.schemas.workflow import WorkflowResponse, WorkflowClarifyRequest, WorkflowActionEditRequest, AuditLogResponse, WorkflowState, DashboardStats, DocumentInfo, OCRInfo, DocumentType
from app.services.workflow_engine import WorkflowEngine

router = APIRouter()

def map_workflow_to_response(workflow: Workflow) -> WorkflowResponse:
    doc_info = DocumentInfo(
        type=DocumentType(workflow.document_type) if workflow.document_type else DocumentType.UNKNOWN,
        confidence=workflow.classification_confidence,
        reason=workflow.classification_reason
    ) if workflow.document_type else None

    ocr_info = OCRInfo(raw_text=workflow.raw_ocr_text) if workflow.raw_ocr_text else None

    return WorkflowResponse(
        id=workflow.id,
        state=WorkflowState(workflow.state),
        original_filename=workflow.original_filename,
        file_hash=workflow.file_hash,
        file_size=workflow.file_size,
        image_width=workflow.image_width,
        image_height=workflow.image_height,
        ocr_provider=workflow.ocr_provider,
        document=doc_info,
        ocr=ocr_info,
        normalized_text=workflow.normalized_text,
        extraction=workflow.extracted_data,
        field_confidence=workflow.field_confidence,
        provenance=workflow.provenance,
        missing_info=workflow.missing_info,
        recommended_action=workflow.recommended_action,
        draft_message=workflow.draft_message,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        error_message=workflow.error_message
    )

import hashlib

@router.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    os.makedirs("uploads", exist_ok=True)
    secure_filename = os.path.basename(file.filename)
    file_content = await file.read()
    file_size = len(file_content)
    file_hash = hashlib.sha256(file_content).hexdigest()

    import io
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(file_content))
        width, height = img.size
    except:
        width, height = None, None

    engine = WorkflowEngine(db)
    workflow = engine.start_workflow(secure_filename, file_hash, file_size, width, height)

    with open(workflow.file_path, "wb") as f:
        f.write(file_content)

    return map_workflow_to_response(workflow)

@router.post("/workflows/{workflow_id}/process", response_model=WorkflowResponse)
def process_workflow(workflow_id: int, db: Session = Depends(get_db)):
    engine = WorkflowEngine(db)
    workflow = engine.process_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return map_workflow_to_response(workflow)

@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return map_workflow_to_response(workflow)

@router.post("/workflows/{workflow_id}/clarify", response_model=WorkflowResponse)
def clarify_workflow(workflow_id: int, request: WorkflowClarifyRequest, db: Session = Depends(get_db)):
    engine = WorkflowEngine(db)
    try:
        workflow = engine.clarify(workflow_id, request.fields)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return map_workflow_to_response(workflow)

@router.post("/workflows/{workflow_id}/approve", response_model=WorkflowResponse)
def approve_workflow(workflow_id: int, request: WorkflowActionEditRequest, db: Session = Depends(get_db)):
    engine = WorkflowEngine(db)
    workflow = engine.approve(workflow_id, request.action, request.message)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return map_workflow_to_response(workflow)

@router.post("/workflows/{workflow_id}/reject", response_model=WorkflowResponse)
def reject_workflow(workflow_id: int, db: Session = Depends(get_db)):
    engine = WorkflowEngine(db)
    workflow = engine.reject(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return map_workflow_to_response(workflow)

@router.get("/workflows", response_model=List[WorkflowResponse])
def list_workflows(db: Session = Depends(get_db)):
    workflows = db.query(Workflow).order_by(Workflow.created_at.desc()).all()
    return [map_workflow_to_response(w) for w in workflows]

@router.get("/dashboard-stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    processed = db.query(Workflow).count()
    completed = db.query(Workflow).filter(Workflow.state == WorkflowState.COMPLETED.value).count()
    needs_review = db.query(Workflow).filter(Workflow.state.in_([WorkflowState.NEEDS_CLARIFICATION.value, WorkflowState.HUMAN_REVIEW.value])).count()
    blocked = db.query(Workflow).filter(Workflow.state.in_([WorkflowState.FAILED.value, WorkflowState.ERROR_RECOVERY.value])).count()

    recent_workflows = db.query(Workflow).order_by(Workflow.created_at.desc()).limit(10).all()

    return DashboardStats(
        processed=processed,
        completed=completed,
        needs_review=needs_review,
        blocked=blocked,
        recent_workflows=[map_workflow_to_response(w) for w in recent_workflows]
    )

@router.get("/workflows/{workflow_id}/audit", response_model=List[AuditLogResponse])
def get_workflow_audit(workflow_id: int, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).filter(AuditLog.workflow_id == workflow_id).order_by(AuditLog.created_at.asc()).all()
    return logs

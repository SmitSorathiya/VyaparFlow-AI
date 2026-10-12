from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum

class WorkflowState(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    CLASSIFIED = "CLASSIFIED"
    EXTRACTED = "EXTRACTED"
    VALIDATING = "VALIDATING"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    READY_FOR_ACTION = "READY_FOR_ACTION"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ERROR_RECOVERY = "ERROR_RECOVERY"

class DocumentType(str, Enum):
    CUSTOMER_ORDER = "CUSTOMER_ORDER"
    BILL = "BILL"
    INVOICE = "INVOICE"
    PAYMENT_SCREENSHOT = "PAYMENT_SCREENSHOT"
    HANDWRITTEN_NOTE = "HANDWRITTEN_NOTE"
    BUSINESS_NOTE = "BUSINESS_NOTE"
    UNKNOWN = "UNKNOWN"

class DocumentInfo(BaseModel):
    type: DocumentType = DocumentType.UNKNOWN
    confidence: Optional[float] = None
    reason: Optional[str] = None

class OCRInfo(BaseModel):
    raw_text: str

class WorkflowResponse(BaseModel):
    id: int
    state: WorkflowState
    original_filename: str
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    ocr_provider: Optional[str] = None
    document: Optional[DocumentInfo] = None
    ocr: Optional[OCRInfo] = None
    normalized_text: Optional[str] = None
    extraction: Optional[Dict[str, Any]] = None
    field_confidence: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None
    missing_info: Optional[List[str]] = None
    recommended_action: Optional[str] = None
    draft_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

class WorkflowClarifyRequest(BaseModel):
    fields: Dict[str, Any]

class WorkflowActionEditRequest(BaseModel):
    action: Optional[str] = None
    message: Optional[str] = None

class AuditLogResponse(BaseModel):
    id: int
    workflow_id: int
    state: WorkflowState
    message: str
    created_at: datetime

    class Config:
        from_attributes = True

class DashboardStats(BaseModel):
    processed: int
    completed: int
    needs_review: int
    blocked: int
    recent_workflows: List[WorkflowResponse]

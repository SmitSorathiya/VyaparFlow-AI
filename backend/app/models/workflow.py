from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, index=True)
    original_filename = Column(String)
    file_path = Column(String)
    file_hash = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)

    ocr_provider = Column(String, nullable=True)
    raw_ocr_text = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)

    document_type = Column(String, nullable=True)
    classification_confidence = Column(Float, nullable=True)
    classification_reason = Column(Text, nullable=True)

    extracted_data = Column(JSON, nullable=True)
    field_confidence = Column(JSON, nullable=True)
    missing_info = Column(JSON, nullable=True)
    provenance = Column(JSON, nullable=True)

    recommended_action = Column(String, nullable=True)
    draft_message = Column(Text, nullable=True)

    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    audit_logs = relationship("AuditLog", back_populates="workflow", cascade="all, delete-orphan")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"))
    state = Column(String)
    message = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    workflow = relationship("Workflow", back_populates="audit_logs")

class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(Text)
    input_file = Column(String)
    expected_document_type = Column(String)
    expected_state = Column(String)

    actual_state = Column(String, nullable=True)
    passed = Column(Integer, nullable=True)
    result_notes = Column(Text, nullable=True)

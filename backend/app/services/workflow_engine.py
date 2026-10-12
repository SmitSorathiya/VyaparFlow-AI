from sqlalchemy.orm import Session
from app.models.workflow import Workflow, AuditLog
from app.schemas.workflow import WorkflowState, DocumentType, DocumentInfo
from app.core.config import settings
from app.services.mock_ai import MockAIProvider
from app.services.gemini_ai import GeminiAIService
from app.services.vision import VisionService
from app.services.ocr import OCRService
from app.services.image_analysis import ImageAnalysisService
from datetime import datetime, timezone
import json
import re

class WorkflowEngine:
    def __init__(self, db: Session, force_demo: bool = False):
        self.db = db
        self.force_demo = force_demo
        self.mock_ai = MockAIProvider()
        self.real_ai = GeminiAIService()
        self.ocr = OCRService()
        self.vision = VisionService()

    def _log(self, workflow_id: int, state: WorkflowState, message: str):
        log = AuditLog(workflow_id=workflow_id, state=state.value, message=message)
        self.db.add(log)
        self.db.commit()

    def start_workflow(self, filename: str, file_hash: str = None, file_size: int = None, image_width: int = None, image_height: int = None) -> Workflow:
        workflow = Workflow(
            state=WorkflowState.RECEIVED.value,
            original_filename=filename,
            file_path="",  # temporary, will be updated
            file_hash=file_hash,
            file_size=file_size,
            image_width=image_width,
            image_height=image_height
        )
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)

        # update with unique path
        import os
        workflow.file_path = f"uploads/{workflow.id}_{os.path.basename(filename)}"
        self.db.commit()

        self._log(workflow.id, WorkflowState.RECEIVED, "Image received")
        return workflow

    def _get_ai_service(self, filename: str):
        is_demo_sample = filename in ["blurry-order.jpg", "clear-order.jpg", "incomplete-order.jpg", "invoice.jpg", "sensitive-pii.jpg"]
        if (settings.DEMO_MODE or self.force_demo) and is_demo_sample:
            return self.mock_ai, True
        return self.real_ai, False

    @staticmethod
    def _required_fields(doc_type: DocumentType):
        return {
            DocumentType.CUSTOMER_ORDER: ["customer_name", "product", "quantity", "delivery_date", "amount"],
            DocumentType.BUSINESS_NOTE: ["customer_name", "product", "quantity", "date", "amount"],
            DocumentType.INVOICE: ["supplier", "total"],
            DocumentType.PAYMENT_SCREENSHOT: ["amount"],
            DocumentType.UNKNOWN: ["document_type"],
        }.get(doc_type, [])

    def _validate(self, doc_type: DocumentType, data: dict, field_confidence: dict):
        missing = []
        for field in self._required_fields(doc_type):
            value = data.get(field)
            metadata = field_confidence.get(field, {})
            if value in (None, "", []) or metadata.get("status") in {"AMBIGUOUS", "NOT_PRESENT"}:
                missing.append(field)
        return missing

    @staticmethod
    def _normalize_human_value(field: str, value):
        if field == "amount":
            cleaned = re.sub(r"[^0-9.]", "", str(value))
            if not cleaned:
                raise ValueError("Amount must be a number")
            amount = float(cleaned)
            if amount <= 0:
                raise ValueError("Amount must be greater than zero")
            return int(amount) if amount.is_integer() else amount
        return value

    def process_workflow(self, workflow_id: int) -> Workflow:
        workflow = self.db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow:
            return None

        ai_service, is_demo = self._get_ai_service(workflow.original_filename)

        # PROCESSING - OCR
        workflow.state = WorkflowState.PROCESSING.value
        workflow.error_message = None
        workflow.missing_info = None
        self.db.commit()
        self._log(workflow.id, WorkflowState.PROCESSING, "Started Local OCR processing")

        try:
            analysis = None
            if not is_demo and isinstance(self.vision, VisionService):
                analysis, cached = ImageAnalysisService().analyze(workflow.file_path, workflow.file_hash)
                raw_text = analysis['raw_text']
                workflow.ocr_provider = 'GeminiVision'
                self._log(workflow.id, WorkflowState.PROCESSING,
                          'Reused recognition for verified identical image bytes' if cached else 'Read and interpreted the uploaded image in one vision request')
            elif not is_demo:
                self._log(workflow.id, WorkflowState.PROCESSING, "Using Cloud Vision API for high accuracy OCR.")
                raw_text = self.vision.process(workflow.original_filename, workflow.file_path)

                # Fallback to local if vision fails
                if not raw_text or len(raw_text.strip()) < 5:
                    self._log(workflow.id, WorkflowState.PROCESSING, "Cloud Vision insufficient. Falling back to Local OCR.")
                    raw_text = self.ocr.process(workflow.original_filename, workflow.file_path, is_demo_sample=False)
                    workflow.ocr_provider = "LocalOCR"
                else:
                    workflow.ocr_provider = "CloudVision"
            else:
                raw_text = self.ocr.process(workflow.original_filename, workflow.file_path, is_demo_sample=True)
                workflow.ocr_provider = "MockOCR"

            workflow.raw_ocr_text = raw_text
            self.db.commit()

            if workflow.ocr_provider == 'LocalOCR' and workflow.document_type == DocumentType.CUSTOMER_ORDER.value and not re.search(r'\d+(?:\.\d+)?\s*(?:kg|g|units?|pcs?)\b', raw_text or '', re.IGNORECASE):
                workflow.state = WorkflowState.FAILED.value
                workflow.error_message = 'Handwriting recognition is unavailable and local OCR could not read this order reliably. Please retry processing.'
                workflow.missing_info = None
                self.db.commit()
                self._log(workflow.id, WorkflowState.FAILED, workflow.error_message)
                return workflow

            if not raw_text or len(raw_text.strip()) == 0:
                workflow.state = WorkflowState.NEEDS_CLARIFICATION.value
                workflow.error_message = "Image quality is too low to reliably extract information."
                self.db.commit()
                self._log(workflow.id, WorkflowState.NEEDS_CLARIFICATION, "OCR extracted no text. Clarification required.")
                return workflow

            # CLASSIFICATION
            doc_info = DocumentInfo(**analysis['document']) if analysis else ai_service.classify(raw_text)
            # If classification is temporarily unavailable, retain a valid type
            # already established for this workflow instead of discarding all
            # extraction structure and asking for every field again.
            if doc_info.type == DocumentType.UNKNOWN and workflow.document_type:
                try:
                    prior_type = DocumentType(workflow.document_type)
                    if prior_type != DocumentType.UNKNOWN:
                        doc_info = DocumentInfo(
                            type=prior_type,
                            confidence=workflow.classification_confidence or 0.0,
                            reason=workflow.classification_reason or "Previously classified document",
                        )
                except ValueError:
                    pass
            workflow.document_type = doc_info.type.value
            workflow.classification_confidence = doc_info.confidence
            workflow.classification_reason = doc_info.reason
            if doc_info.type == DocumentType.UNKNOWN:
                workflow.state = WorkflowState.FAILED.value
                workflow.error_message = "Could not classify the document. " + (doc_info.reason or "Please retry processing.")
                workflow.missing_info = None
                self.db.commit()
                self._log(workflow.id, WorkflowState.FAILED, workflow.error_message)
                return workflow
            workflow.state = WorkflowState.CLASSIFIED.value
            self.db.commit()
            self._log(workflow.id, WorkflowState.CLASSIFIED, f"Document classified as {doc_info.type.value} ({doc_info.confidence*100}%)")

            # EXTRACTION
            if analysis:
                extracted_data, _, normalized_text, field_confidence, provenance = ai_service._parse_extraction_payload(analysis, raw_text, doc_info.type)
            else:
                extracted_data, _, normalized_text, field_confidence, provenance = ai_service.extract(raw_text, doc_info.type)
            missing = self._validate(doc_info.type, extracted_data, field_confidence)

            workflow.extracted_data = extracted_data
            workflow.normalized_text = normalized_text
            workflow.field_confidence = field_confidence
            workflow.provenance = provenance
            workflow.state = WorkflowState.EXTRACTED.value
            self.db.commit()
            self._log(workflow.id, WorkflowState.EXTRACTED, "Information extracted based on document type")

            # VALIDATING
            workflow.state = WorkflowState.VALIDATING.value
            self.db.commit()
            self._log(workflow.id, WorkflowState.VALIDATING, "Validating extracted data")

            if missing:
                workflow.missing_info = missing
                workflow.state = WorkflowState.NEEDS_CLARIFICATION.value
                self.db.commit()
                self._log(workflow.id, WorkflowState.NEEDS_CLARIFICATION, f"Missing required information: {', '.join(missing)}")
                return workflow
            else:
                workflow.missing_info = None

            # READY_FOR_ACTION
            action, message = ai_service.generate_action(doc_info.type, extracted_data)
            workflow.recommended_action = action
            workflow.draft_message = message
            workflow.state = WorkflowState.READY_FOR_ACTION.value
            self.db.commit()
            self._log(workflow.id, WorkflowState.READY_FOR_ACTION, f"Action generated: {action}")

            # Move to HUMAN_REVIEW immediately after generation
            workflow.state = WorkflowState.HUMAN_REVIEW.value
            self.db.commit()
            self._log(workflow.id, WorkflowState.HUMAN_REVIEW, "Awaiting human review")

        except Exception as e:
            workflow.state = WorkflowState.FAILED.value
            workflow.error_message = ('Image recognition timed out. Please retry processing.'
                                      if isinstance(e, TimeoutError) or 'timed out' in str(e).lower() else str(e))
            self.db.commit()
            self._log(workflow.id, WorkflowState.FAILED, f"Pipeline Failure: {str(e)}")

        return workflow

    def clarify(self, workflow_id: int, fields: dict) -> Workflow:
        workflow = self.db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow:
            return None

        ai_service, _ = self._get_ai_service(workflow.original_filename)

        self._log(workflow.id, WorkflowState.NEEDS_CLARIFICATION, f"User provided missing information: {json.dumps(fields)}")

        data = dict(workflow.extracted_data or {})
        prov = dict(workflow.provenance or {})
        confidence = dict(workflow.field_confidence or {})
        for k, v in fields.items():
            data[k] = self._normalize_human_value(k, v)
            prov[k] = "HUMAN_INPUT"
            confidence[k] = {"score": 1.0, "status": "PRESENT", "evidence": "HUMAN_INPUT"}

        workflow.extracted_data = data
        workflow.provenance = prov
        workflow.field_confidence = confidence

        doc_type = DocumentType(workflow.document_type)
        missing = self._validate(doc_type, data, confidence)
        workflow.missing_info = missing or None
        if missing:
            workflow.state = WorkflowState.NEEDS_CLARIFICATION.value
            self.db.commit()
            self._log(workflow.id, WorkflowState.NEEDS_CLARIFICATION, f"Still missing required information: {', '.join(missing)}")
            return workflow

        action, message = ai_service.generate_action(doc_type, data)
        workflow.recommended_action = action
        workflow.draft_message = message
        workflow.state = WorkflowState.HUMAN_REVIEW.value
        self.db.commit()

        self._log(workflow.id, WorkflowState.READY_FOR_ACTION, f"Action generated after clarification: {action}")
        self._log(workflow.id, WorkflowState.HUMAN_REVIEW, "Awaiting human review")

        return workflow

    def approve(self, workflow_id: int, action: str = None, message: str = None) -> Workflow:
        workflow = self.db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow:
            return None

        if action:
            workflow.recommended_action = action
        if message:
            workflow.draft_message = message

        workflow.state = WorkflowState.APPROVED.value
        self.db.commit()
        self._log(workflow.id, WorkflowState.APPROVED, "Action approved by user")

        workflow.state = WorkflowState.COMPLETED.value
        self.db.commit()
        self._log(workflow.id, WorkflowState.COMPLETED, "Workflow completed successfully")

        return workflow

    def reject(self, workflow_id: int) -> Workflow:
        workflow = self.db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow:
            return None

        workflow.state = WorkflowState.FAILED.value
        workflow.error_message = "Rejected by user"
        self.db.commit()
        self._log(workflow.id, WorkflowState.FAILED, "Action rejected by user. Workflow stopped.")

        return workflow

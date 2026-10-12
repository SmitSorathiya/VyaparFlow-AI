from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.core.database import get_db
from app.models.workflow import EvaluationCase
from app.schemas.workflow import WorkflowState, DocumentType
from app.services.workflow_engine import WorkflowEngine

router = APIRouter()

# Setup test cases on memory/DB for demo
TEST_CASES = [
    {
        "name": "Clear Customer Order",
        "input_file": "clear-order.jpg",
        "expected_document_type": DocumentType.CUSTOMER_ORDER.value,
        "expected_state": WorkflowState.HUMAN_REVIEW.value
    },
    {
        "name": "Blurry Image",
        "input_file": "blurry-order.jpg",
        "expected_document_type": DocumentType.CUSTOMER_ORDER.value,
        "expected_state": WorkflowState.NEEDS_CLARIFICATION.value
    },
    {
        "name": "Missing Required Field (Amount)",
        "input_file": "incomplete-order.jpg",
        "expected_document_type": DocumentType.CUSTOMER_ORDER.value,
        "expected_state": WorkflowState.NEEDS_CLARIFICATION.value
    },
    {
        "name": "Clear Invoice",
        "input_file": "invoice.jpg",
        "expected_document_type": DocumentType.INVOICE.value,
        "expected_state": WorkflowState.HUMAN_REVIEW.value
    }
]

@router.post("/run")
def run_evaluation(db: Session = Depends(get_db)):
    results = []
    engine = WorkflowEngine(db, force_demo=True)

    for tc in TEST_CASES:
        workflow = engine.start_workflow(tc["input_file"])
        workflow = engine.process_workflow(workflow.id)

        passed = True
        notes = []

        if workflow.document_type != tc["expected_document_type"]:
            passed = False
            notes.append(f"Expected doc type {tc['expected_document_type']}, got {workflow.document_type}")

        if workflow.state != tc["expected_state"]:
            passed = False
            notes.append(f"Expected state {tc['expected_state']}, got {workflow.state}")

        results.append({
            "case": tc["name"],
            "input": tc["input_file"],
            "passed": passed,
            "actual_state": workflow.state,
            "actual_doc_type": workflow.document_type,
            "notes": notes
        })

    return {"results": results}

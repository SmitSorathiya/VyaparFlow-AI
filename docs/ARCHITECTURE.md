# Architecture notes

The browser uploads multipart image data to FastAPI. The backend calculates SHA-256, creates a workflow, and saves the image under its unique workflow path. Records/files stay local; ordinary recognition sends the image to Gemini.

ImageAnalysisService verifies the file hash, then reads a matching model/version cache entry or makes one HTTPS request. The provider returns literal transcription, normalized text, classification, and fields with evidence/status/confidence. Only that provider response is cached, never human input or approval state.

GeminiAIService._parse_extraction_payload rejects unsupported or low-confidence fields, requires monetary evidence for amounts, normalizes conservatively, and guards against assigning one product occurrence as a customer. WorkflowEngine._validate identifies missing required fields. Clarification merges human values with HUMAN_INPUT provenance and revalidates before drafting an action.

Workflow stores both document and workflow data. AuditLog.workflow_id associates events. EvaluationCase exists as a legacy model; the evaluation route currently returns mock case results directly. There is no global latest-document lookup.

React uses page-local state and API reads, polling during processing/clarification and refreshing on window focus. There is no localStorage/sessionStorage workflow cache. The frontend assumes localhost:8000 for the backend.

Demo recognition is gated by demo mode and exact reserved sample filenames. Evaluation explicitly selects mock providers without changing global settings. Real uploads use actual image bytes; avoid reserved filenames for real documents in demo mode.

This is a local prototype, not an authenticated multi-user service. See the README for setup, checks, external-provider data handling, and limitations.

# VyaparFlow AI

An image-to-action worker for micro-entrepreneurs. Upload a handwritten order, invoice, or business note; inspect the extracted fields; supply missing information; and approve a suggested action.

Built with React, TypeScript, FastAPI, SQLAlchemy, SQLite, and Gemini vision. Files and workflow records live locally; real image recognition uses a cloud provider. The app drafts actions but does not send messages or execute payments.

## The problem

A shopkeeper's order note often fits on one line. Turning that line into a useful record is harder than just reading the handwriting: a number might be a quantity or a price, and a missing amount should stay missing until someone supplies it.

VyaparFlow focuses on that step between reading a document and acting on it. The user can check the image against the extracted record, correct missing details, and review the draft before approving it.

## Where to start

For a quick walkthrough, follow the offline setup below and try **Clear Order**, then **Missing Amount**. Neither needs an API key. To inspect the implementation, start with these files:

- [workflow_engine.py](backend/app/services/workflow_engine.py): validation, clarification, provenance, and state transitions.
- [image_analysis.py](backend/app/services/image_analysis.py): one image request and content-hash caching.
- [gemini_ai.py](backend/app/services/gemini_ai.py): field evidence checks and supported shorthand interpretation.
- [WorkflowDetail.tsx](frontend/src/pages/WorkflowDetail.tsx): extraction display, missing-field inputs, and approval.
- [test_extraction_workflow.py](backend/test_extraction_workflow.py): examples of accepted and rejected interpretations.

[Design decisions](docs/DESIGN.md) explains the tradeoffs and the edge cases behind the extraction rules. [Architecture notes](docs/ARCHITECTURE.md) describes how the pieces connect.

## Features

- Dashboard with image uploads, sample workflows, and recent activity.
- Original image, raw transcription, normalized text, structured fields, confidence/evidence, and audit trail.
- Clarification forms for missing or ambiguous fields, including numeric amounts.
- Editable action drafts with human approval and rejection.
- Offline sample evaluation and automated regression tests.

| Image content | Intended clarification |
| --- | --- |
| Harry -> 1 kg Papad -> Tomorrow | Amount only |
| Wheat -> 28/09/2026 | Customer name, quantity, and amount |
| Adam -> Rice -> 450 -> Tomorrow | Quantity only; the supported four-part shorthand treats the third segment as total amount |
| Same shorthand with a separate 2 kg quantity branch | No missing fields; proceed to review |
| Rajesh -> 2 kg Rice -> Rs 310 -> Friday | Proceed to review |

Real-upload responses are not hardcoded to these examples. Recognition varies with handwriting and provider availability.

The arrow format is an explicit application convention: `customer -> product -> total -> delivery date`. A separate quantity branch such as `-> 2 kg` is supported. Other unlabelled numbers remain ambiguous; the app does not treat every number as a price. Prefer units and a currency marker in real documents when possible.

## Quick start: offline sample demo

Prerequisites: Git, Python 3.11+ (3.12 recommended), Node.js 22.12+ and npm. No Gemini key or Tesseract installation is required for offline samples or tests.

```sh
git clone https://github.com/SmitSorathiya/VyaparFlow-AI.git
cd VyaparFlow-AI
```

Run the backend from the `backend` directory: database and upload paths are relative to it.

Windows PowerShell:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\venv\Scripts\python.exe generate_images.py
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

macOS / Linux:

```sh
cd backend
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
./venv/bin/python generate_images.py
./venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

In a second terminal, from the repository root:

```sh
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Frontend: http://127.0.0.1:5173
API documentation: http://127.0.0.1:8000/docs

1. Select **Sample: Clear Order**, then **Start Processing**.
2. Review the fields and draft; edit if needed and approve.
3. Try **Sample: Missing Amount**, enter an amount, and continue to review.
4. Open **Evaluation** to run four deterministic sample cases without spending API quota.

`DEMO_MODE=true` applies only to reserved sample filenames: `clear-order.jpg`, `blurry-order.jpg`, `incomplete-order.jpg`, `invoice.jpg`, and `sensitive-pii.jpg`. These use synthetic mock responses. Ordinary uploads still use real vision. Avoid reserved filenames for real documents while demo mode is enabled. Evaluation always uses mock samples and creates workflow records locally.

## Real image uploads

Edit the ignored `backend/.env`:

```dotenv
DEMO_MODE=false
GEMINI_API_KEY=your_own_key
GEMINI_VISION_MODEL=gemini-3.5-flash-lite
VISION_PROVIDER=gemini
TESSERACT_CMD_PATH=
```

Use a model your Google project can access, and restart the backend after editing environment settings. A new image is sent to Gemini in one HTTPS request for transcription, classification, and extraction. Free-tier quotas and network access still apply; a new key on the same project does not reset quota.

Successful recognition is cached locally using the model/version and a verified SHA-256 hash of image bytes. Identical images can reuse provider responses; human input and workflow state are never cached. Cache files live under `backend/uploads/recognition_cache/`. Removing an individual cache entry forces fresh recognition for that image.

Tesseract is optional for legacy OCR paths. Install it separately and set `TESSERACT_CMD_PATH` if needed; common Windows installation paths are discovered automatically. It does not provide Gemini-quality handwriting recognition or bypass cloud quota errors in the active real-upload pipeline.

## Architecture

```text
Upload -> RECEIVED -> PROCESSING -> CLASSIFIED -> EXTRACTED -> VALIDATING
                                                             |
                         missing/ambiguous fields -> NEEDS_CLARIFICATION
                                                             |
                                     human input + revalidation
                                                             |
                             READY_FOR_ACTION -> HUMAN_REVIEW
                                                             |
                                     APPROVED -> COMPLETED
Provider/read failures -> FAILED (retry available)
```

Approval completes a local record. Rejection marks it failed. Raw transcription remains separate from interpreted text. Accepted fields require evidence; human corrections receive `HUMAN_INPUT` provenance.

```text
backend/
  app/api/               Upload, process, clarify, review, dashboard, evaluation
  app/services/          Vision, extraction, validation, workflow engine, mocks
  app/models/            Workflow and audit persistence
  app/schemas/           Requests, responses, states
  app/core/              Settings and database initialization
  generate_images.py     Synthetic demo-image generator
  test_*.py              Offline regression tests
frontend/src/
  pages/                 Dashboard, Workflows, WorkflowDetail, Evaluation
  services/api.ts        Local API client
  types/                 Frontend data shapes
docs/                    Architecture notes and original brief
```

Each workflow owns a unique image path (`uploads/<workflow_id>_<filename>`), hash, OCR/normalized text, classification, extracted fields, confidence/provenance, missing fields, and action drafts. Audit rows reference `workflow_id`. There is no separate document table or global latest-document lookup. SQLite tables are created on startup.

## Tests and checks

From `backend`, using your virtual-environment Python:

```sh
python -m unittest discover -v -p "test_*.py"
```

No key or network is needed. The current suite has 20 tests covering absent/explicit amounts, human-input provenance, normalization without replacing raw text, customer/product disambiguation, numeric roles, separate quantity branches, content-hash isolation, quota handling, and offline evaluation. Mocked responses test workflow correctness; they are not a handwriting-accuracy benchmark.

From `frontend`:

```sh
npm run build
npm run lint
```

GitHub Actions runs backend tests and frontend checks on pushes and pull requests.

## API overview

| Endpoint | Purpose |
| --- | --- |
| `POST /api/workflows` | Upload an image |
| `POST /api/workflows/{id}/process` | Recognize, extract, validate |
| `GET /api/workflows/{id}` | Get workflow state/data |
| `POST /api/workflows/{id}/clarify` | Submit `{"fields": {...}}` |
| `POST /api/workflows/{id}/approve` | Approve optional edited action/message |
| `POST /api/workflows/{id}/reject` | Reject |
| `GET /api/workflows/{id}/audit` | Audit trail |
| `GET /api/dashboard-stats` | Totals and recent workflows |
| `POST /api/evaluation/run` | Offline sample evaluation |

## Limitations and data handling

- Local development prototype: no authentication, tenant isolation, rate limiting, or production hardening. Uploads are served by the local backend and CORS is permissive.
- Real images are sent to Google's Gemini API. Local storage includes original images, recognition caches, SQLite records, and audit logs. Assess this data handling before using sensitive documents.
- The sensitive-PII sample is illustrative, not a production PII-redaction system or compliance guarantee.
- Dashboard health badges are presentation placeholders, not live provider probes.
- Confidence includes provider scores and heuristic scores from normalization rules; it is not statistically calibrated. Missing amounts are not estimated from products or quantities. The documented arrow shorthand is a format assumption, not a general solution for every handwritten layout.
- Compatibility services still import the legacy Google SDK; the active real-image path uses HTTPS via `httpx`.
- Environment files, documents, databases, caches, dependencies, logs, and installers are excluded from Git. No personal workflow history is needed for the demo.

If sample images fail to load, run `generate_images.py` from `backend`. For HTTP 429, wait for quota reset; retries do not restore quota. For connection errors, confirm both servers are running on ports 8000 and 5173.

# Design decisions

## The record needs to be checkable

The original image, raw transcription, interpreted text, and structured fields answer different questions. Keeping them separate lets a reviewer check where a value came from. Correcting a delivery-date spelling should not erase the text that was actually read.

Each accepted field has evidence, confidence, and provenance. A human-supplied value gets `HUMAN_INPUT`; it does not acquire OCR provenance just because it is stored next to OCR fields.

## Missing and ambiguous values stop the workflow

The workflow requires customer, product, quantity, delivery date, and amount for customer orders. A product/date business note also requires customer, quantity, and amount before its action can be reviewed. Different document types have different required fields.

Validation runs after extraction and after clarification. Drafting happens only after required fields pass validation. Approval is a separate user action. This keeps a complete-looking draft from hiding an incomplete record.

The clarification form is driven by `missing_info`, not a fixed list of inputs. For example, a product and date should survive a request for the missing customer name, quantity, and amount.

## A number needs a role

The extraction rules distinguish `2 kg`, `Qty: 2`, and an unlabelled `450`. A unit or label establishes quantity. A currency marker or amount label establishes money. A bare number is not enough by itself.

There is one supported shorthand convention: `customer -> product -> total -> delivery date`. In that complete sequence, the third segment is the total. A quantity can appear on a separate branch. The parser checks the customer, product, and date against accepted fields before using the number; unrelated extra lines do not qualify.

This is a deliberate format constraint. It works for the demonstrated order notes, but other writing conventions may need clarification or a different parser. The code must not assume a price from a product name, silently invent a unit, or reuse another workflow's amount.

## One recognition request per new image

The active path asks Gemini for transcription, classification, and structured fields together. Separate requests for each stage would spend more quota and add more opportunities for a partial failure. The backend still records classification, extraction, and validation as separate workflow stages.

Successful provider responses are cached by verified image bytes, model, and cache version. Re-uploading identical bytes can reuse recognition, but it creates its own workflow. Human corrections and approval state are never copied from that cache. Quota errors are failures, not document text.

The cache currently uses a manually maintained version in the key. A change that needs fresh model recognition should bump that version; parser-only changes can revalidate an existing response.

## Local storage and cloud recognition

SQLite and filesystem storage keep the local setup small. The application is not fully offline: arbitrary real uploads go to Gemini. Offline evaluation uses synthetic filenames and mock providers, and verifies workflow behavior rather than handwriting accuracy.

Tesseract remains available in legacy code, but its output on these handwritten notes was not reliable enough to substitute for failed cloud recognition. The active image path reports provider failures instead of presenting that fallback text as a valid order.

## What needs work next

The main gaps are authentication and upload access controls, explicit retention/deletion, a real handwriting evaluation dataset, and support for more document layouts. The current tests cover workflow decisions and known failure cases using mocked provider responses. They do not establish an overall recognition accuracy score.

The dashboard's provider-health labels are placeholders. State transitions are implemented in the service, but the API does not yet enforce every allowed transition against out-of-order callers. Those are known prototype limits, not production guarantees.

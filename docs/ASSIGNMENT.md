# Original project brief: VyaparFlow AI

This records intended goals, not a claim that every requirement is implemented. See the README and ARCHITECTURE.md for verified behavior and limitations.

**Goal:**
Improve the speed and accuracy with which micro-entrepreneurs process physical business documents (like handwritten orders or bills) into actionable next steps, without losing control over the final action.

**User:**
A micro-entrepreneur or shopkeeper with limited technical comfort, using a basic smartphone or laptop, potentially with poor internet connectivity.

**System:**
The worker operates as a bridge between physical document capture (input) and a digital record/communication system (e.g., messaging a customer or logging a bill).

**Inputs:**
Images or scanned documents of customer orders, bills, invoices, or handwritten notes.

**Outputs:**
A structured recommendation for action (e.g., a drafted customer follow-up message) ready for human approval.

**Decisions:**
It can recommend document classification, extract relevant fields, determine if critical information is missing, and draft a business action based on the extracted data.

**Constraints:**
It CANNOT send messages automatically, invent missing values, guess low-confidence data, or make financial decisions without explicit human approval.

**Device Constraint:**
Must support low-end devices, emphasizing simple UI, minimal animations, and clear text.

**Definition of Done:**
The workflow is complete ONLY when the extracted data is validated, an action is recommended, and the human user explicitly hits "Approve" (or "Reject").

**Privacy / DPDP:**
- Storage is local; real image recognition sends the image to Gemini.
- The sensitive mock sample is illustrative; production PII detection/redaction is not implemented.
- Original image is kept locally.
- Images, recognition caches, and workflow/audit records are retained locally. Retention and authenticated access controls are future work.

**Escalation:**
The worker stops and escalates to the human immediately if critical information (e.g., amount, delivery date) is missing or blurry, asking for manual clarification.

**Success Metric:**
Reduction in time spent manually typing out customer follow-ups or logging bills, measured by the number of completed and approved AI-assisted workflows versus abandoned or manually handled ones.

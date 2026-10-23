import google.generativeai as genai
import json
import re
from difflib import SequenceMatcher
from typing import Tuple, List, Dict, Any
from app.schemas.workflow import DocumentType, DocumentInfo
from app.core.config import settings
import traceback
import threading
from queue import Queue

class GeminiAIService:
    def __init__(self):
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY, transport="rest")
        self.model = genai.GenerativeModel(settings.GEMINI_VISION_MODEL)

    def classify(self, raw_ocr_text: str) -> DocumentInfo:
        try:
            prompt = f"""
            Classify the following OCR text extracted from an image into one of these types:
            - CUSTOMER_ORDER
            - BUSINESS_NOTE
            - INVOICE
            - PAYMENT_SCREENSHOT
            - HANDWRITTEN_NOTE
            - UNKNOWN

            A note that identifies a customer/person, a product and quantity, and a requested
            delivery date is a CUSTOMER_ORDER even when its amount is absent. Missing required
            fields affect validation; they must not change an otherwise evident document type.

            OCR TEXT:
            \"\"\"{raw_ocr_text}\"\"\"

            Return ONLY a JSON object:
            {{
                "type": "BUSINESS_NOTE",
                "confidence": 0.95,
                "reason": "Contains a product and a date but lacks order structure"
            }}
            """
            response = self._generate_content(prompt)
            data = json.loads(response.text.strip())

            doc_type_str = data.get("type", "UNKNOWN")
            try:
                doc_type = DocumentType(doc_type_str)
            except ValueError:
                doc_type = DocumentType.UNKNOWN

            return DocumentInfo(
                type=doc_type,
                confidence=data.get("confidence", 0.0),
                reason=data.get("reason", "")
            )
        except Exception as e:
            with open("gemini_error.log", "a") as f:
                f.write(traceback.format_exc() + "\n")
            return DocumentInfo(type=DocumentType.UNKNOWN, confidence=0.0, reason=str(e))

    @staticmethod
    def _evidence_is_present(raw_text: str, evidence: Any) -> bool:
        if not isinstance(evidence, str) or not evidence.strip():
            return False
        compact_raw = re.sub(r"\s+", " ", raw_text).casefold()
        compact_evidence = re.sub(r"\s+", " ", evidence).strip().casefold()
        return compact_evidence in compact_raw

    @staticmethod
    def _amount_matches_evidence(value: Any, evidence: str) -> bool:
        if not isinstance(value, (int, float)):
            return False
        if not re.search(r"(?:₹|\brs\.?\b|\binr\b|\bamount\b|\bamt\b|\btotal\b)", evidence or "", re.IGNORECASE):
            return False
        expected = format(float(value), "g")
        observed = {number.replace(",", "") for number in re.findall(r"\d+(?:[.,]\d+)?", evidence or "")}
        return expected in observed

    def _parse_extraction_payload(self, payload: Dict[str, Any], raw_ocr_text: str, doc_type: DocumentType):
        normalized_text = payload.get("normalized_text") or raw_ocr_text
        extracted_data: Dict[str, Any] = {}
        confidence: Dict[str, Any] = {}
        provenance: Dict[str, str] = {}

        for field_name, details in (payload.get("fields") or {}).items():
            if not isinstance(details, dict):
                continue
            value = details.get("value")
            evidence = details.get("evidence")
            status = str(details.get("status", "AMBIGUOUS")).upper()
            try:
                score = float(details.get("confidence", 0.0))
            except (TypeError, ValueError):
                score = 0.0

            supported = self._evidence_is_present(raw_ocr_text, evidence)
            if field_name == "amount" and value is not None:
                supported = supported and self._amount_matches_evidence(value, evidence)
            if field_name == "quantity" and value is not None:
                numeric_quantity = str(value).strip()
                if re.fullmatch(r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?', numeric_quantity):
                    # An unlabelled number could be a price, count, weight, etc.
                    # Accept a bare count only when the source names its role.
                    labelled = re.search(
                        r'\b(?:qty|quantity|count)\s*[:=\-]?\s*'
                        + re.escape(numeric_quantity) + r'(?![\d.])',
                        raw_ocr_text,
                        re.IGNORECASE,
                    )
                    supported = supported and bool(labelled)
            if status != "PRESENT" or score < 0.65 or not supported:
                value = None

            extracted_data[field_name] = value
            confidence[field_name] = {
                "score": score,
                "status": status if supported or (status == "NOT_PRESENT" and value is None) else "AMBIGUOUS",
                "evidence": evidence if supported else None,
            }
            if value is not None:
                provenance[field_name] = "VISION/OCR/NORMALIZATION"

        # Some vision responses return the interpreted text but omit the per-field
        # objects. Recover only unambiguous evidence from the actual OCR string;
        # never invent customer, quantity, or amount values. This keeps visible
        # product/date fields from being incorrectly requested as clarification.
        if doc_type == DocumentType.BUSINESS_NOTE:
            source_text = raw_ocr_text or normalized_text
            source_text = source_text.replace("\u2192", "->")
            date_match = re.search(r"(?<!\d)(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})(?!\d)", source_text)
            if date_match and extracted_data.get("date") in (None, "", []):
                date_value = date_match.group(0)
                extracted_data["date"] = date_value
                confidence["date"] = {
                    "score": 0.9,
                    "status": "PRESENT",
                    "evidence": date_value,
                }
                provenance["date"] = "VISION/OCR/NORMALIZATION"

            if extracted_data.get("product") in (None, "", []):
                segments = [segment.strip() for segment in re.split(r"\s*(?:->|→)\s*", source_text) if segment.strip()]
                candidates = []
                for segment in segments:
                    if re.search(r"(?<!\d)(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})(?!\d)", segment):
                        continue
                    if re.search(r"(?:₹|rs\.?|inr|amount|amt|total)\s*[\d,]+(?:\.\d+)?", segment, re.IGNORECASE):
                        continue
                    if re.search(r"\b\d+(?:\.\d+)?\s*(?:kg|kgs|g|gram|grams|unit|units|pcs?|pieces?)\b", segment, re.IGNORECASE):
                        continue
                    if segment and segment not in candidates:
                        candidates.append(segment)
                if len(candidates) == 1:
                    product_value = candidates[0]
                    extracted_data["product"] = product_value
                    confidence["product"] = {
                        "score": 0.82,
                        "status": "PRESENT",
                        "evidence": product_value,
                    }
                    provenance["product"] = "VISION/OCR/NORMALIZATION"

        if doc_type == DocumentType.CUSTOMER_ORDER:
            source_text = raw_ocr_text or normalized_text
            source_text = source_text.replace("\u2192", "->")

            # Recover clear order structure when the provider supplied text but
            # omitted its field metadata. Each value must still be evidenced by
            # an exact OCR substring; ambiguous values remain missing.
            # Do not override the provider's explicit NOT_PRESENT/AMBIGUOUS
            # customer result. Position alone is not evidence of a person.
            if 'customer_name' not in (payload.get('fields') or {}) and extracted_data.get("customer_name") in (None, "", []):
                first_segment = re.split(r"\s*(?:->|→)\s*", source_text, maxsplit=1)[0].strip()
                if (
                    first_segment
                    and '->' in source_text
                    and re.search(r'\d+(?:\.\d+)?\s*(?:kgs?|grams?|g|units?|pcs?|pieces?)\b', source_text, re.IGNORECASE)
                    and first_segment.casefold() != str(extracted_data.get('product') or '').strip().casefold()
                    and not re.search(r"\d", first_segment)
                    and not re.search(r"\b(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", first_segment, re.IGNORECASE)
                ):
                    extracted_data["customer_name"] = first_segment
                    confidence["customer_name"] = {"score": 0.86, "status": "PRESENT", "evidence": first_segment}
                    provenance["customer_name"] = "VISION/OCR/NORMALIZATION"

            quantity_matches = list(re.finditer(
                r"(?P<quantity>\d+(?:\.\d+)?\s*(?:kg|kgs|g|gram|grams|unit|units|pcs?|pieces?))\s*"
                r"(?P<product>[A-Za-z][A-Za-z ]*?)(?=\s*(?:->|→|\n|$))",
                source_text,
                re.IGNORECASE,
            ))
            if quantity_matches:
                evidence_parts = [match.group(0).strip() for match in quantity_matches]
                if extracted_data.get("quantity") in (None, "", []):
                    extracted_data["quantity"] = ", ".join(match.group("quantity").strip() for match in quantity_matches)
                    confidence["quantity"] = {
                        "score": 0.88,
                        "status": "PRESENT",
                        "evidence": source_text,
                    }
                    provenance["quantity"] = "VISION/OCR/NORMALIZATION"
                if extracted_data.get("product") in (None, "", []):
                    extracted_data["product"] = ", ".join(match.group("product").strip() for match in quantity_matches)
                    confidence["product"] = {
                        "score": 0.84,
                        "status": "PRESENT",
                        "evidence": source_text,
                    }
                    provenance["product"] = "VISION/OCR/NORMALIZATION"

            if extracted_data.get("delivery_date") in (None, "", []):
                date_match = re.search(
                    r"(?<!\d)(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})(?!\d)|"
                    r"\b(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
                    source_text,
                    re.IGNORECASE,
                )
                if date_match:
                    date_value = date_match.group(0)
                    extracted_data["delivery_date"] = date_value
                    confidence["delivery_date"] = {"score": 0.88, "status": "PRESENT", "evidence": date_value}
                    provenance["delivery_date"] = "VISION/OCR/NORMALIZATION"

        # One occurrence cannot independently establish both a person and a
        # product. Preserve the evidenced product and ask for the person.
        customer = extracted_data.get('customer_name')
        product = extracted_data.get('product')
        if isinstance(customer, str) and isinstance(product, str) and customer.strip().casefold() == product.strip().casefold():
            occurrences = len(re.findall(r'(?<!\w)' + re.escape(customer.strip()) + r'(?!\w)', raw_ocr_text, re.IGNORECASE))
            if occurrences < 2:
                extracted_data['customer_name'] = None
                confidence['customer_name'] = {'score': 0.0, 'status': 'NOT_PRESENT', 'evidence': None}
                provenance.pop('customer_name', None)

        # Providers sometimes repeat an explicit quantity in the product field.
        # Remove only an identical, evidenced quantity prefix.
        product = extracted_data.get('product')
        quantity = extracted_data.get('quantity')
        if isinstance(product, str) and isinstance(quantity, str):
            compact_quantity = re.sub(r'\s+', '', quantity).casefold()
            prefix = re.match(r'^(\d+(?:\.\d+)?\s*(?:kgs?|grams?|g|units?|pcs?|pieces?))\s+(.+)$', product, re.IGNORECASE)
            if prefix and re.sub(r'\s+', '', prefix.group(1)).casefold() == compact_quantity:
                extracted_data['product'] = prefix.group(2)

        # Normalize small spelling errors in a closed date vocabulary only when
        # an accepted, evidenced field has a unique high-similarity match.
        date_words = ['Today', 'Tomorrow', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for date_field in ('delivery_date', 'date'):
            value = extracted_data.get(date_field)
            if isinstance(value, str) and value.isalpha():
                ranked = sorted(
                    ((SequenceMatcher(None, value.casefold(), word.casefold()).ratio(), word) for word in date_words),
                    reverse=True,
                )
                if ranked[0][0] >= 0.85 and ranked[0][0] - ranked[1][0] >= 0.15:
                    corrected = ranked[0][1]
                    extracted_data[date_field] = corrected
                    normalized_text = re.sub(r'\b' + re.escape(value) + r'\b', corrected, normalized_text, flags=re.IGNORECASE)

        # Supported shorthand convention: customer -> product -> total -> date.
        # The main line may have separate quantity-only branches. Read the total
        # from the main sequence while retaining independently evidenced units.
        if doc_type == DocumentType.CUSTOMER_ORDER and extracted_data.get('amount') is None:
            lines = [line.strip() for line in raw_ocr_text.splitlines() if line.strip()]
            main_line = lines[0] if lines else ''
            quantity_branch = r'(?:(?:->|\u2192)\s*)?(?:(?:qty|quantity)\s*[:=]?\s*)?\d+(?:\.\d+)?\s*(?:kgs?|grams?|g|units?|pcs?|pieces?|litres?|liters?|ml|l)'
            branches_are_quantities = all(re.fullmatch(quantity_branch, line, re.IGNORECASE) for line in lines[1:])
            branches_are_evidenced = len(lines) <= 1 or extracted_data.get('quantity') is not None
            segments = [part.strip() for part in re.split(r'\s*(?:->|\u2192)\s*', main_line)]
            if len(segments) == 4 and branches_are_quantities and branches_are_evidenced:
                customer, product, total, date = segments
                customer_matches = customer.casefold() == str(extracted_data.get('customer_name') or '').casefold()
                product_matches = product.casefold() == str(extracted_data.get('product') or '').casefold()
                date_matches = date.casefold() in {
                    str(extracted_data.get('delivery_date') or '').casefold(),
                    str(confidence.get('delivery_date', {}).get('evidence') or '').casefold(),
                }
                numeric_total = re.fullmatch(r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?', total)
                if customer_matches and product_matches and date_matches and numeric_total:
                    amount = float(total.replace(',', ''))
                    if amount > 0:
                        extracted_data['amount'] = int(amount) if amount.is_integer() else amount
                        confidence['amount'] = {
                            'score': 0.85, 'status': 'PRESENT', 'evidence': main_line,
                            'interpretation': 'customer -> product -> total amount -> delivery date',
                        }
                        provenance['amount'] = 'VISION/OCR/NORMALIZATION'
                        if extracted_data.get('quantity') is None:
                            confidence['quantity'] = {'score': 0.85, 'status': 'NOT_PRESENT', 'evidence': None}

        required = {
            DocumentType.CUSTOMER_ORDER: ["customer_name", "product", "quantity", "delivery_date", "amount"],
            DocumentType.BUSINESS_NOTE: ["customer_name", "product", "quantity", "date", "amount"],
            DocumentType.INVOICE: ["supplier", "total"],
            DocumentType.PAYMENT_SCREENSHOT: ["amount"],
        }.get(doc_type, [])
        missing = [field for field in required if extracted_data.get(field) in (None, "", [])]
        return extracted_data, missing, normalized_text, confidence, provenance

    def extract(self, raw_ocr_text: str, doc_type: DocumentType):
        try:
            schema_map = {
                DocumentType.CUSTOMER_ORDER: {
                    "customer_name": "string", "product": "string",
                    "quantity": "string including unit", "amount": "number",
                    "delivery_date": "string", "notes": "string",
                },
                DocumentType.BUSINESS_NOTE: {
                    "customer_name": "string", "product": "string", "quantity": "string including unit", "date": "string",
                    "note": "string", "amount": "number",
                },
                DocumentType.INVOICE: {
                    "supplier": "string", "invoice_number": "string", "date": "string",
                    "items": "list of item objects", "subtotal": "number",
                    "tax": "number", "total": "number",
                },
                DocumentType.PAYMENT_SCREENSHOT: {
                    "payer": "string", "amount": "number", "date": "string",
                    "transaction_reference": "string",
                },
                DocumentType.HANDWRITTEN_NOTE: {
                    "text": "string", "entities": "list of strings",
                    "date": "string", "note": "string",
                },
            }
            if doc_type == DocumentType.UNKNOWN:
                return {"raw_text": raw_ocr_text, "reason": "Unclassified"}, ["document_type"], raw_ocr_text, {}, {}

            schema = schema_map.get(doc_type, schema_map[DocumentType.HANDWRITTEN_NOTE])
            prompt = f"""
            Interpret OCR text for document type {doc_type.value}. Distinguish carefully between:
            - information present with clear OCR: extract it;
            - information present but recognizably OCR-corrupted: normalize it only with strong contextual support;
            - ambiguous information: return null;
            - information not present: return null.

            Never infer an amount from a product, quantity, prior knowledge, or a typical value.
            Every non-null field must quote a short exact substring of the OCR as evidence.
            Confidence is from 0 to 1. Status is PRESENT, AMBIGUOUS, or NOT_PRESENT.

            Return ONLY JSON with "normalized_text" and a "fields" object. Each field must contain
            "value", "evidence", "confidence", and "status". Include every field in this schema:
            {json.dumps(schema, indent=2)}

            OCR TEXT:
            \"\"\"{raw_ocr_text}\"\"\"
            """
            response = self._generate_content(prompt)
            return self._parse_extraction_payload(json.loads(response.text.strip()), raw_ocr_text, doc_type)
        except Exception:
            with open("gemini_error.log", "a") as f:
                f.write(traceback.format_exc() + "\n")
            # Preserve a usable, evidence-based result if the remote provider is
            # unavailable (for example, quota exhaustion). The local parser only
            # accepts explicit OCR patterns and never fabricates an amount.
            return self._parse_extraction_payload(
                {"normalized_text": raw_ocr_text, "fields": {}},
                raw_ocr_text,
                doc_type,
            )

    def _generate_content(self, prompt: str):
        result = Queue(maxsize=1)

        def call_model():
            try:
                result.put((True, self.model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"},
                    request_options={"timeout": 30},
                )))
            except Exception as error:
                result.put((False, error))

        worker = threading.Thread(target=call_model, daemon=True)
        worker.start()
        worker.join(30)
        if worker.is_alive():
            raise TimeoutError("Gemini AI request timed out")
        succeeded, response = result.get_nowait()
        if not succeeded:
            raise response
        return response

    def generate_action(self, doc_type: DocumentType, data: Dict[str, Any]) -> Tuple[str, str]:
        if doc_type == DocumentType.CUSTOMER_ORDER:
            return (
                "create customer follow-up message",
                f"Follow up with {data.get('customer_name', 'Customer')} regarding "
                f"{data.get('quantity', '')} {data.get('product', 'their order')} "
                f"for ₹{data.get('amount')} due {data.get('delivery_date', 'on the agreed date')}."
            )
        elif doc_type == DocumentType.BUSINESS_NOTE:
            return "create reminder", f"Reminder for {data.get('product', 'Item')} ({data.get('quantity', '')}) on {data.get('date', 'Unknown Date')} for {data.get('customer_name', 'the customer')}"
        elif doc_type == DocumentType.INVOICE:
            return "summarize supplier bill", f"Record invoice from {data.get('supplier', 'Unknown')} for {data.get('total', 'Unknown amount')}"
        elif doc_type == DocumentType.PAYMENT_SCREENSHOT:
            return "verify payment", f"Verify payment of {data.get('amount', 'Unknown amount')} from {data.get('payer', 'Unknown')}"
        elif doc_type == DocumentType.HANDWRITTEN_NOTE:
            return "save business note", f"Note: {data.get('note', 'General notes')}"

        return "create internal business note", "Review document."

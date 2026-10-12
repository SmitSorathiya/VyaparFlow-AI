import json
import re
from typing import Dict, Any, Tuple, List
from app.schemas.workflow import DocumentType, DocumentInfo

class MockAIProvider:
    def classify(self, text: str) -> DocumentInfo:
        text_lower = text.lower()
        if "order" in text_lower or "kg" in text_lower or "del" in text_lower or "harry" in text_lower or "smith" in text_lower:
            return DocumentInfo(type=DocumentType.CUSTOMER_ORDER, confidence=0.95, reason="Mock keyword match")
        if "supplier" in text_lower or "invoice" in text_lower or "total" in text_lower:
            return DocumentInfo(type=DocumentType.INVOICE, confidence=0.95, reason="Mock keyword match")
        if "aadhar" in text_lower:
            return DocumentInfo(type=DocumentType.UNKNOWN, confidence=0.0, reason="PII detected")

        return DocumentInfo(type=DocumentType.CUSTOMER_ORDER, confidence=0.8, reason="Defaulting to CUSTOMER_ORDER")

    def extract(self, text: str, doc_type: DocumentType):
        text_lower = text.lower()
        result = {}
        missing_fields = []

        if doc_type == DocumentType.CUSTOMER_ORDER:
            # Customer name regex
            name_match = re.search(r'(?i)(?:customer|cstm|name)[:\-]?\s*([a-zA-Z\s]+)', text)
            if name_match and len(name_match.group(1).strip()) > 2:
                result["customer_name"] = name_match.group(1).strip()
            elif "rajesh" in text_lower:
                result["customer_name"] = "Rajesh"
            elif "smith" in text_lower:
                result["customer_name"] = "Smith"
            elif "harry" in text_lower:
                result["customer_name"] = "Harry"
            else:
                missing_fields.append("customer_name")

            # Items regex
            result["product"] = None
            result["quantity"] = None
            item_matches = re.finditer(r'(?i)(\d+(?:\.\d+)?)\s*(kg|g|ltr|pcs|pack|box)?\s+([a-zA-Z]+)', text)
            found_items = False
            for match in item_matches:
                qty, unit, name = match.groups()
                result["product"] = name.strip().capitalize()
                result["quantity"] = f"{format(float(qty), 'g')} {unit or 'units'}"
                found_items = True
                break

            if not found_items:
                missing_fields.extend(["product", "quantity"])

            # Amount regex
            amt_match = re.search(r'(?i)(?:rs|inr|₹|amount|amt|total)[:\-]?\s*(\d+(?:\.\d+)?)', text)
            if amt_match:
                result["amount"] = float(amt_match.group(1))
            elif "310" in text_lower:
                result["amount"] = 310.0
            else:
                missing_fields.append("amount")

            # Date regex
            date_match = re.search(r'(?i)(?:del|delivery|date|on)[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)', text)
            if not date_match:
                date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)

            if date_match:
                result["delivery_date"] = date_match.group(1).strip()
            elif "tomorrow" in text_lower or "tommorow" in text_lower:
                result["delivery_date"] = "Tomorrow"
            elif "monday" in text_lower:
                result["delivery_date"] = "Monday"
            else:
                missing_fields.append("delivery_date")

        elif doc_type in [DocumentType.BILL, DocumentType.INVOICE]:
            if "abc traders" in text_lower:
                result["supplier"] = "ABC Traders"
            if "1500" in text_lower:
                result["total"] = 1500.0

        normalized_text = text
        confidence = {
            key: {"score": 1.0, "status": "PRESENT", "evidence": "mock sample"}
            for key, value in result.items() if value is not None
        }
        provenance = {key: "MOCK_OCR" for key, value in result.items() if value is not None}
        return result, missing_fields, normalized_text, confidence, provenance

    def generate_action(self, doc_type: DocumentType, data: Dict[str, Any]) -> Tuple[str, str]:
        if doc_type == DocumentType.CUSTOMER_ORDER:
            action = "create customer follow-up message"
            message = f"Hi {data.get('customer_name', 'Customer')}, your order for "
            if data.get('quantity') or data.get('product'):
                message += f"{data.get('quantity', '')} {data.get('product', '')} "
            if data.get('amount'):
                message += f"for ₹{data['amount']} "
            message += "is noted. Please confirm your delivery address."
            return action, message

        elif doc_type in [DocumentType.BILL, DocumentType.INVOICE]:
            return "summarize supplier bill", f"Record bill of ₹{data.get('total', '0')} from {data.get('supplier', 'Unknown')}"

        return "create internal business note", "Review document."

    def detect_pii(self, text: str) -> bool:
        if "aadhar" in text.lower() or "phone:" in text.lower():
            return True
        return False

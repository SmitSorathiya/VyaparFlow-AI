import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.schemas.workflow import DocumentInfo, DocumentType, WorkflowState
from app.services.gemini_ai import GeminiAIService
from app.services.workflow_engine import WorkflowEngine


class FakeVision:
    def __init__(self, text):
        self.text = text

    def process(self, filename, file_path):
        return self.text


class PayloadAI:
    def __init__(self, payload, doc_type=DocumentType.CUSTOMER_ORDER):
        self.payload = payload
        self.doc_type = doc_type
        self.parser = GeminiAIService.__new__(GeminiAIService)

    def classify(self, raw_text):
        return DocumentInfo(type=self.doc_type, confidence=0.92, reason="Test document")

    def extract(self, raw_text, doc_type):
        return self.parser._parse_extraction_payload(self.payload, raw_text, doc_type)

    def generate_action(self, doc_type, data):
        return GeminiAIService.generate_action(self.parser, doc_type, data)


def field(value, evidence, confidence=0.9, status="PRESENT"):
    return {"value": value, "evidence": evidence, "confidence": confidence, "status": status}


class ExtractionWorkflowTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def run_case(self, raw_text, payload, doc_type=DocumentType.CUSTOMER_ORDER):
        worker = WorkflowEngine(self.db)
        worker.real_ai = PayloadAI(payload, doc_type)
        worker.vision = FakeVision(raw_text)
        workflow = worker.start_workflow("handwritten-order.jpg")
        return worker, worker.process_workflow(workflow.id)

    def test_missing_amount_requires_clarification_then_accepts_human_amount(self):
        raw = "hat6y ->\nIng Papad -> Tommosow"
        payload = {
            "normalized_text": "Harry -> 1 kg Papad -> Tomorrow",
            "fields": {
                "customer_name": field("Harry", "hat6y", 0.78),
                "product": field("Papad", "Papad", 0.99),
                "quantity": field("1 kg", "Ing Papad", 0.76),
                "delivery_date": field("Tomorrow", "Tommosow", 0.88),
                "amount": field(None, None, 1.0, "NOT_PRESENT"),
            },
        }
        worker, workflow = self.run_case(raw, payload)

        self.assertEqual(workflow.state, WorkflowState.NEEDS_CLARIFICATION.value)
        self.assertEqual(workflow.extracted_data["customer_name"], "Harry")
        self.assertEqual(workflow.extracted_data["product"], "Papad")
        self.assertEqual(workflow.extracted_data["quantity"], "1 kg")
        self.assertEqual(workflow.extracted_data["delivery_date"], "Tomorrow")
        self.assertIsNone(workflow.extracted_data["amount"])
        self.assertEqual(workflow.missing_info, ["amount"])
        self.assertEqual(workflow.raw_ocr_text, raw)
        self.assertEqual(workflow.normalized_text, payload["normalized_text"])

        workflow = worker.clarify(workflow.id, {"amount": "₹250"})
        self.assertEqual(workflow.state, WorkflowState.HUMAN_REVIEW.value)
        self.assertEqual(workflow.extracted_data["amount"], 250)
        self.assertEqual(workflow.provenance["amount"], "HUMAN_INPUT")
        for name in ("customer_name", "product", "quantity", "delivery_date"):
            self.assertEqual(workflow.provenance[name], "VISION/OCR/NORMALIZATION")

    def test_explicit_amount_does_not_require_clarification(self):
        raw = "Rajesh -> 2 kg Rice -> ₹310 -> Friday"
        payload = {
            "normalized_text": raw,
            "fields": {
                "customer_name": field("Rajesh", "Rajesh"),
                "product": field("Rice", "Rice"),
                "quantity": field("2 kg", "2 kg"),
                "delivery_date": field("Friday", "Friday"),
                "amount": field(310, "₹310"),
            },
        }
        _, workflow = self.run_case(raw, payload)

        self.assertEqual(workflow.state, WorkflowState.HUMAN_REVIEW.value)
        self.assertEqual(workflow.extracted_data["customer_name"], "Rajesh")
        self.assertEqual(workflow.extracted_data["product"], "Rice")
        self.assertEqual(workflow.extracted_data["quantity"], "2 kg")
        self.assertEqual(workflow.extracted_data["delivery_date"], "Friday")
        self.assertEqual(workflow.extracted_data["amount"], 310)
        self.assertIsNone(workflow.missing_info)

    def test_amount_without_monetary_evidence_is_rejected(self):
        parser = GeminiAIService.__new__(GeminiAIService)
        raw = "Customer -> 1 kg Product -> Tomorrow"
        payload = {
            "normalized_text": raw,
            "fields": {"amount": field(1, "1 kg")},
        }
        data, missing, _, _, _ = parser._parse_extraction_payload(
            payload, raw, DocumentType.CUSTOMER_ORDER
        )
        self.assertIsNone(data["amount"])
        self.assertIn("amount", missing)

    def test_date_normalization_preserves_raw_evidence_and_missing_amount(self):
        raw = 'Alex -> 3 kg Beans -> Tommorow'
        payload = {'normalized_text': raw, 'fields': {
            'customer_name': field('Alex', 'Alex'),
            'product': field('Beans', 'Beans'),
            'quantity': field('3 kg', '3 kg'),
            'delivery_date': field('Tommorow', 'Tommorow'),
            'amount': field(None, None, 1.0, 'NOT_PRESENT'),
        }}
        _, workflow = self.run_case(raw, payload)
        self.assertEqual(workflow.raw_ocr_text, raw)
        self.assertEqual(workflow.extracted_data['delivery_date'], 'Tomorrow')
        self.assertIn('Tomorrow', workflow.normalized_text)
        self.assertEqual(workflow.field_confidence['delivery_date']['evidence'], 'Tommorow')
        self.assertEqual(workflow.field_confidence['amount']['status'], 'NOT_PRESENT')
        self.assertEqual(workflow.missing_info, ['amount'])

    def test_business_note_requests_customer_quantity_and_amount(self):
        raw = "Wheat -> 28/09/2026"
        payload = {
            "normalized_text": raw,
            "fields": {
                "customer_name": field(None, None, 0.0, "NOT_PRESENT"),
                "product": field("Wheat", "Wheat"),
                "quantity": field(None, None, 0.0, "NOT_PRESENT"),
                "date": field("28/09/2026", "28/09/2026"),
                "amount": field(None, None, 0.0, "NOT_PRESENT"),
            },
        }
        _, workflow = self.run_case(raw, payload, DocumentType.BUSINESS_NOTE)

        self.assertEqual(workflow.state, WorkflowState.NEEDS_CLARIFICATION.value)
        self.assertEqual(workflow.missing_info, ["customer_name", "quantity", "amount"])

    def test_business_note_recovers_unambiguous_product_and_date_when_provider_omits_fields(self):
        raw = "Wheat -> 28/09/2026"
        payload = {"normalized_text": raw, "fields": {}}
        _, workflow = self.run_case(raw, payload, DocumentType.BUSINESS_NOTE)

        self.assertEqual(workflow.extracted_data["product"], "Wheat")
        self.assertEqual(workflow.extracted_data["date"], "28/09/2026")
        self.assertEqual(workflow.missing_info, ["customer_name", "quantity", "amount"])

    def test_customer_order_recovers_all_present_fields_when_provider_omits_fields(self):
        raw = "Smith -> 5kg rice -> Monday\n      -> 2kg wheat"
        payload = {"normalized_text": raw, "fields": {}}
        _, workflow = self.run_case(raw, payload, DocumentType.CUSTOMER_ORDER)

        self.assertEqual(workflow.extracted_data["customer_name"], "Smith")
        self.assertEqual(workflow.extracted_data["product"], "rice, wheat")
        self.assertEqual(workflow.extracted_data["quantity"], "5kg, 2kg")
        self.assertEqual(workflow.extracted_data["delivery_date"], "Monday")
        self.assertEqual(workflow.missing_info, ["amount"])

    def test_product_date_order_does_not_invent_customer_from_first_segment(self):
        for product, customer_status in [('Wheat', 'NOT_PRESENT'), ('Lentils', 'AMBIGUOUS')]:
            with self.subTest(product=product):
                raw = product + ' -> 28/09/2026'
                payload = {'normalized_text': raw, 'fields': {
                    'customer_name': field(None, None, 1.0, customer_status),
                    'product': field(product, product),
                    'quantity': field(None, None, 1.0, 'NOT_PRESENT'),
                    'delivery_date': field('28/09/2026', '28/09/2026'),
                    'amount': field(None, None, 1.0, 'NOT_PRESENT'),
                }}
                worker, workflow = self.run_case(raw, payload)
                self.assertIsNone(workflow.extracted_data['customer_name'])
                self.assertEqual(workflow.extracted_data['product'], product)
                self.assertEqual(workflow.missing_info, ['customer_name', 'quantity', 'amount'])
                workflow = worker.clarify(workflow.id, {'customer_name': 'Asha', 'quantity': '2 kg', 'amount': 250})
                self.assertEqual(workflow.state, WorkflowState.HUMAN_REVIEW.value)
                self.assertEqual(workflow.provenance['product'], 'VISION/OCR/NORMALIZATION')
                self.assertEqual(workflow.provenance['customer_name'], 'HUMAN_INPUT')

    def test_one_occurrence_cannot_be_customer_and_product(self):
        raw = 'Millet -> Friday'
        payload = {'normalized_text': raw, 'fields': {
            'customer_name': field('Millet', 'Millet'),
            'product': field('Millet', 'Millet'),
            'delivery_date': field('Friday', 'Friday'),
        }}
        _, workflow = self.run_case(raw, payload)
        self.assertIsNone(workflow.extracted_data['customer_name'])
        self.assertEqual(workflow.extracted_data['product'], 'Millet')
        self.assertNotIn('customer_name', workflow.provenance)
        self.assertEqual(workflow.missing_info, ['customer_name', 'quantity', 'amount'])

    def test_unlabelled_number_is_not_assumed_quantity_and_human_can_confirm_amount(self):
        # Outside the supported four-part shorthand, numeric roles stay ambiguous.
        raw = 'Alex -> Lentils -> 725 -> reference ABC -> Friday'
        payload = {'normalized_text': raw, 'fields': {
            'customer_name': field('Alex', 'Alex'),
            'product': field('Lentils', 'Lentils'),
            'quantity': field('725', '725'),
            'delivery_date': field('Friday', 'Friday'),
            'amount': field(None, None, 1.0, 'NOT_PRESENT'),
        }}
        worker, workflow = self.run_case(raw, payload)
        self.assertIsNone(workflow.extracted_data['quantity'])
        self.assertEqual(workflow.missing_info, ['quantity', 'amount'])
        workflow = worker.clarify(workflow.id, {'amount': 725})
        self.assertEqual(workflow.extracted_data['amount'], 725)
        self.assertEqual(workflow.provenance['amount'], 'HUMAN_INPUT')
        self.assertEqual(workflow.missing_info, ['quantity'])
        self.assertEqual(workflow.raw_ocr_text, raw)
        workflow = worker.clarify(workflow.id, {'quantity': '3 kg'})
        self.assertEqual(workflow.state, WorkflowState.HUMAN_REVIEW.value)

    def test_explicitly_labelled_quantity_count_is_preserved(self):
        raw = 'Alex -> Lentils -> Qty: 2 -> Rs 725 -> Friday'
        payload = {'normalized_text': raw, 'fields': {
            'customer_name': field('Alex', 'Alex'),
            'product': field('Lentils', 'Lentils'),
            'quantity': field('2', '2'),
            'delivery_date': field('Friday', 'Friday'),
            'amount': field(725, 'Rs 725'),
        }}
        _, workflow = self.run_case(raw, payload)
        self.assertEqual(workflow.extracted_data['quantity'], '2')
        self.assertEqual(workflow.state, WorkflowState.HUMAN_REVIEW.value)

    def test_shorthand_total_is_read_for_each_new_workflow_without_reusing_amounts(self):
        for total in ('725', '980', '1,250.50'):
            with self.subTest(total=total):
                raw = 'Alex -> Lentils -> ' + total + ' -> Friday'
                payload = {'normalized_text': raw, 'fields': {
                    'customer_name': field('Alex', 'Alex'),
                    'product': field('Lentils', 'Lentils'),
                    'quantity': field(total, total),
                    'delivery_date': field('Friday', 'Friday'),
                    'amount': field(None, None, 1.0, 'NOT_PRESENT'),
                }}
                worker, workflow = self.run_case(raw, payload)
                self.assertEqual(workflow.extracted_data['amount'], float(total.replace(',', '')))
                self.assertIsNone(workflow.extracted_data['quantity'])
                self.assertEqual(workflow.missing_info, ['quantity'])
                self.assertEqual(workflow.provenance['amount'], 'VISION/OCR/NORMALIZATION')
                self.assertEqual(workflow.field_confidence['amount']['evidence'], raw)
                workflow = worker.clarify(workflow.id, {'quantity': '2 kg'})
                self.assertEqual(workflow.state, WorkflowState.HUMAN_REVIEW.value)

    def test_shorthand_does_not_reinterpret_an_explicit_quantity_as_amount(self):
        raw = 'Alex -> Lentils -> 2 kg -> Friday'
        payload = {'normalized_text': raw, 'fields': {
            'customer_name': field('Alex', 'Alex'),
            'product': field('Lentils', 'Lentils'),
            'quantity': field('2 kg', '2 kg'),
            'delivery_date': field('Friday', 'Friday'),
            'amount': field(None, None, 1.0, 'NOT_PRESENT'),
        }}
        _, workflow = self.run_case(raw, payload)
        self.assertIsNone(workflow.extracted_data['amount'])
        self.assertEqual(workflow.extracted_data['quantity'], '2 kg')
        self.assertEqual(workflow.missing_info, ['amount'])

    def test_shorthand_with_quantity_branch_proceeds_directly_to_review(self):
        for total, quantity in [('725', '3 kg'), ('980.50', '4 kg')]:
            with self.subTest(total=total, quantity=quantity):
                main = 'Alex -> Lentils -> ' + total + ' -> Friday'
                raw = main + '\n -> ' + quantity
                payload = {'normalized_text': raw, 'fields': {
                    'customer_name': field('Alex', 'Alex'),
                    'product': field('Lentils', 'Lentils'),
                    'quantity': field(quantity, quantity),
                    'delivery_date': field('Friday', 'Friday'),
                    'amount': field(float(total), total),
                }}
                _, workflow = self.run_case(raw, payload)
                self.assertEqual(workflow.extracted_data['amount'], float(total))
                self.assertEqual(workflow.extracted_data['quantity'], quantity)
                self.assertEqual(workflow.state, WorkflowState.HUMAN_REVIEW.value)
                self.assertIsNone(workflow.missing_info)
                self.assertEqual(workflow.field_confidence['quantity']['evidence'], quantity)
                self.assertEqual(workflow.field_confidence['amount']['evidence'], main)

    def test_unrelated_numeric_branch_does_not_activate_shorthand_total(self):
        raw = 'Alex -> Lentils -> 725 -> Friday\nReference 123'
        payload = {'normalized_text': raw, 'fields': {
            'customer_name': field('Alex', 'Alex'),
            'product': field('Lentils', 'Lentils'),
            'delivery_date': field('Friday', 'Friday'),
            'amount': field(None, None, 1.0, 'NOT_PRESENT'),
        }}
        _, workflow = self.run_case(raw, payload)
        self.assertIsNone(workflow.extracted_data['amount'])
        self.assertIn('amount', workflow.missing_info)


if __name__ == "__main__":
    unittest.main()

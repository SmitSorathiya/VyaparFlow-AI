"""Single-request image reading with content-addressed provider-result caching."""
import base64
import hashlib
import json
import mimetypes
from pathlib import Path

import httpx

from app.core.config import settings


class ImageAnalysisService:
    def __init__(self, cache_dir='uploads/recognition_cache'):
        self.cache_dir = Path(cache_dir)

    def analyze(self, file_path, expected_hash=None):
        contents = Path(file_path).read_bytes()
        digest = hashlib.sha256(contents).hexdigest()
        if expected_hash and digest != expected_hash:
            raise ValueError('Stored image does not match the uploaded image hash.')
        # Only immutable provider responses are cached. Human input and workflow
        # state are never cached or transferred between workflows.
        model = settings.GEMINI_VISION_MODEL
        cache_key = hashlib.sha256((model + ':v1:' + digest).encode()).hexdigest()
        cache = self.cache_dir / (cache_key + '.json')
        if cache.exists():
            payload = json.loads(cache.read_text(encoding='utf-8'))
            if payload.get('image_hash') == digest:
                return payload['analysis'], True

        prompt = '''Read this actual image and return JSON only. Do not invent absent information.
Return raw_text (literal transcription, plain text arrows ->, no LaTeX),
normalized_text (careful interpretation of obvious spelling/handwriting errors),
document {type, confidence, reason}, and fields.
Document type is CUSTOMER_ORDER, BUSINESS_NOTE, INVOICE, PAYMENT_SCREENSHOT,
HANDWRITTEN_NOTE or UNKNOWN. Orders can lack an amount.
Determine entity roles from context, not arrow position. A product followed only
by a date does not establish a customer name or a quantity. Do not assign the
same single text occurrence to both customer_name and product. If no person is
identified, customer_name must be null with status NOT_PRESENT. Use BUSINESS_NOTE
for a product/date reminder without customer/order structure.
For orders include customer_name, product, quantity, delivery_date, amount, notes.
For business notes include customer_name, product, quantity, date, amount, note.
For invoices include supplier, total, date, items. For payments include payer, amount, date.
Every field is {value, evidence, confidence, status}. Evidence quotes an exact
substring of raw_text. Status is PRESENT, NOT_PRESENT or AMBIGUOUS.
Absent/ambiguous values must be null. Amount must be a number only when explicit
monetary evidence is visible. Never derive amount from quantity, dates, products
or prices remembered from other documents. Normalize clear date spelling errors
and quantity units while retaining literal raw_text and evidence. Confidence 0..1.
Product contains only product names, excluding quantity and unit. Quantity includes
the number and unit, separated by a space.
This app supports the specific shorthand customer -> product -> total amount ->
delivery date. In that complete four-part format, the third standalone number is
the total amount. Quantity may appear on a separate branch/line; preserve it
when explicitly written with a unit or quantity label. Otherwise quantity is
absent. Quote the full main sequence as evidence for the total amount.
Outside that format, an unlabelled standalone number does not establish whether
it is amount or quantity. Without a currency marker, quantity unit, explicit role
label, or other unambiguous evidence, mark its role AMBIGUOUS and leave affected
fields null. Never use one number for both fields or invent a quantity unit.
For multiple products retain all quantities and product names in matching order.'''
        response = httpx.post(
            'https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent',
            headers={'x-goog-api-key': settings.GEMINI_API_KEY},
            json={
                'contents': [{'parts': [
                    {'text': prompt},
                    {'inline_data': {'mime_type': mimetypes.guess_type(file_path)[0] or 'image/jpeg',
                                     'data': base64.b64encode(contents).decode('ascii')}},
                ]}],
                'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0},
            },
            timeout=60,
        )
        if response.status_code == 429:
            raise RuntimeError('Free handwriting-recognition quota is exhausted. Please wait for the quota reset. No reliable image extraction was produced.')
        if response.status_code != 200:
            raise RuntimeError(f'Image recognition is unavailable (HTTP {response.status_code}). Please retry later.')
        parts = response.json().get('candidates', [{}])[0].get('content', {}).get('parts', [])
        text = ''.join(part.get('text', '') for part in parts if not part.get('thought'))
        analysis = json.loads(text)
        if not isinstance(analysis.get('raw_text'), str) or not analysis['raw_text'].strip():
            raise RuntimeError('Image recognition could not read any text reliably.')
        if not isinstance(analysis.get('fields'), dict) or not isinstance(analysis.get('document'), dict):
            raise RuntimeError('Image recognition returned an incomplete response. Please retry.')
        if analysis['document'].get('type') != 'UNKNOWN':
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({'image_hash': digest, 'analysis': analysis}), encoding='utf-8')
        return analysis, False

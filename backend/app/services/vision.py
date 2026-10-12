import google.generativeai as genai
import threading
from queue import Queue
from app.core.config import settings

class VisionProvider:
    def process_image(self, filename: str, file_path: str) -> str:
        raise NotImplementedError()

class GeminiVisionProvider(VisionProvider):
    def __init__(self):
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY, transport="rest")
        # Use the configured vision model for both OCR and interpretation.
        model_name = getattr(settings, "GEMINI_VISION_MODEL", "gemini-3.8-flash")
        self.model = genai.GenerativeModel(model_name)

    def process_image(self, filename: str, file_path: str) -> str:
        try:
            print(f"Uploading {file_path} to Gemini Vision ({self.model.model_name}) for fallback OCR...")
            from PIL import Image
            img = Image.open(file_path)
            prompt = "Extract all handwritten or printed text from this image exactly as written. Return plain text only, with arrows rendered as ->, without Markdown or LaTeX. Preserve layout where possible. Do not invent any words. If there is no text, return empty string."
            result = Queue(maxsize=1)

            def call_model():
                try:
                    result.put((True, self.model.generate_content([img, prompt], request_options={"timeout": 60})))
                except Exception as error:
                    result.put((False, error))

            worker = threading.Thread(target=call_model, daemon=True)
            worker.start()
            worker.join(60)
            if worker.is_alive():
                raise TimeoutError("Gemini Vision timed out")
            succeeded, response = result.get_nowait()
            if not succeeded:
                raise response
            return response.text.strip()
        except Exception as e:
            print(f"Gemini Vision Error: {e}. Falling back to OCR.space API.")
            try:
                import httpx
                with open(file_path, "rb") as f:
                    res = httpx.post(
                        "https://api.ocr.space/parse/image",
                        data={"apikey": "helloworld"},
                        files={"file": f},
                        timeout=12.0
                    ).json()
                if res.get("ParsedResults"):
                    return res["ParsedResults"][0]["ParsedText"].strip()
            except Exception as fallback_e:
                print(f"Fallback OCR.space Error: {fallback_e}")
            return ""

class MockVisionProvider(VisionProvider):
    def process_image(self, filename: str, file_path: str) -> str:
        # Should only be used for testing without API keys
        return ""

class VisionService:
    def __init__(self):
        provider = getattr(settings, "VISION_PROVIDER", "gemini").lower()
        if provider == "gemini":
            self.provider = GeminiVisionProvider()
        else:
            self.provider = MockVisionProvider()

    def process(self, filename: str, file_path: str) -> str:
        return self.provider.process_image(filename, file_path)

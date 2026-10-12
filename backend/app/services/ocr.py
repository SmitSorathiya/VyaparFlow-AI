import os
import shutil
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

class OCRProvider:
    def process_image(self, filename: str, file_path: str) -> str:
        raise NotImplementedError()

class TesseractOCRProvider(OCRProvider):
    def __init__(self):
        configured_path = os.getenv("TESSERACT_CMD_PATH", "")
        tesseract_paths = [
            configured_path,
            shutil.which("tesseract") or "",
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\admin\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
        ]
        # Tesseract's Windows installer records the install directory here.
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Tesseract-OCR") as key:
                install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
                tesseract_paths.insert(0, os.path.join(install_dir, "tesseract.exe"))
        except (ImportError, FileNotFoundError, OSError):
            pass

        for p in tesseract_paths:
            if p and os.path.isfile(p):
                pytesseract.pytesseract.tesseract_cmd = p
                break

    def process_image(self, filename: str, file_path: str) -> str:
        try:
            img = Image.open(file_path)

            # Preprocessing
            new_size = (img.width * 2, img.height * 2)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            gray = img.convert('L')
            enhancer = ImageEnhance.Contrast(gray)
            contrast = enhancer.enhance(2.0)
            denoised = contrast.filter(ImageFilter.MedianFilter(size=3))

            debug_dir = "uploads/debug_ocr"
            os.makedirs(debug_dir, exist_ok=True)
            debug_path = os.path.join(debug_dir, f"preprocessed_{filename}")
            denoised.save(debug_path)

            text = pytesseract.image_to_string(denoised, lang='eng', config='--psm 6')
            return text.strip()
        except Exception as e:
            print(f"Tesseract OCR Error: {e}")
            return ""

class MockOCRProvider(OCRProvider):
    def process_image(self, filename: str, file_path: str) -> str:
        text = filename.lower()
        if "blurry" in text:
            return "Cstm: Rajesh\nPrd: Rice\nQty: 5 kg\nAmt: ??\nDel: ??"
        if "incomplete" in text:
            return "Rajesh\n5 kg rice\ndelivery tomorrow"
        if "order" in text:
            return "Rajesh\n5 kg rice\nRs310\ndelivery tomorrow"
        if "invoice" in text:
            return "Supplier: ABC Traders\nTotal: 1500\nDate: 2023-10-01"
        if "sensitive" in text:
            return "Customer: John\nAadhar: 1234-5678-9012\nPhone: 9876543210"

        return ""

class OCRService:
    def __init__(self):
        self.primary = TesseractOCRProvider()
        self.fallback = MockOCRProvider()

    def process(self, filename: str, file_path: str, is_demo_sample: bool = False) -> str:
        if is_demo_sample:
            print(f"Using Mock OCR for demo sample: {filename}")
            return self.fallback.process_image(filename, file_path)

        text = self.primary.process_image(filename, file_path)
        return text

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import random

os.makedirs("uploads", exist_ok=True)
os.makedirs("demo-data", exist_ok=True)

def create_image(filename, text, size=(400, 300), bg_color=(255, 255, 255), text_color=(0, 0, 0), blur=False, lines=False):
    img = Image.new('RGB', size, color=bg_color)
    draw = ImageDraw.Draw(img)

    # Try to load a default font, otherwise use default
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = ImageFont.load_default()

    if lines:
        for y in range(0, size[1], 20):
            draw.line([(0, y), (size[0], y)], fill=(200, 200, 200), width=1)

    # Draw text
    y_text = 20
    for line in text.split('\n'):
        draw.text((20, y_text), line, font=font, fill=text_color)
        y_text += 30

    if blur:
        img = img.filter(ImageFilter.GaussianBlur(2.5))

    filepath = os.path.join("uploads", filename)
    img.save(filepath, format="JPEG", quality=85)
    print(f"Generated {filepath}")

# 1. Clear Order
create_image("clear-order.jpg",
    "CUSTOMER ORDER\n\nName: Rajesh\nItem: 5 kg Rice\nAmount: Rs. 310\nDelivery: Tomorrow",
    bg_color=(250, 250, 240), lines=True)

# 2. Blurry Order
create_image("blurry-order.jpg",
    "Order Note\n\nCstm: Rajesh\nPrd: Rice (5 kg)\nAmt: ??\nDel: ??",
    blur=True)

# 3. Incomplete Order
create_image("incomplete-order.jpg",
    "Rajesh's Order\n\n- 5 kg rice\n- delivery tomorrow\n\n(No price mentioned)",
    bg_color=(255, 255, 255))

# 4. Invoice
create_image("invoice.jpg",
    "TAX INVOICE\n\nSupplier: ABC Traders\nDate: 2023-10-01\n\nTotal Due: 1500 INR",
    bg_color=(240, 248, 255))

# 5. Sensitive PII
create_image("sensitive-pii.jpg",
    "Customer Application\n\nCustomer: John Doe\nAadhar: 1234-5678-9012\nPhone: 9876543210\nDOB: 01-01-1980",
    bg_color=(255, 240, 240))

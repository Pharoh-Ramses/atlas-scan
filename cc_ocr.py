import pytesseract
from pdf2image import convert_from_path
from PIL import Image, ImageOps, ImageEnhance


def preprocess_image(image):
    # Convert to grayscale
    gray_image = ImageOps.grayscale(image)

    # Increase contrast
    enhancer = ImageEnhance.Contrast(gray_image)
    high_contrast = enhancer.enhance(2.0)

    # Apply adaptive thresholding
    threshold = 200
    binary_image = high_contrast.point(lambda p: p > threshold and 255)

    return binary_image


def post_process_text(text):
    # Remove extra spaces and newlines
    cleaned = ' '.join(text.split())
    # Additional cleaning can be added here if needed
    return cleaned


def cc_ocr(pdf_path, dpi=300):
    try:
        images = convert_from_path(pdf_path, dpi=dpi)
        extracted_data = {}

        if len(images) > 0:
            processed_image = preprocess_image(images[0])

            regions = {
                'patient_name': (655, 361, 1130, 429),
                'date_of_birth': (651, 446, 987, 522),
                'gender': (655, 541, 968, 608),
                'mrn': (650, 1276, 928, 1337),
                'test_name': (649, 1352, 1278, 1405),
                'collection_date': (650, 1493, 1214, 1556),
                'tested_pathogen': (256, 1719, 633, 1776),
                'test_result': (651, 1721, 1196, 1779),
                'reported_date': (647, 1565, 1137, 1628)
            }

            for key, coords in regions.items():
                cropped = processed_image.crop(coords)
                # Adjust OCR settings for better accuracy
                custom_config = r'--oem 3 --psm 6'
                if key == 'gender':
                    custom_config += r' -c tessedit_char_whitelist=FM'
                text = pytesseract.image_to_string(cropped, config=custom_config).strip()
                extracted_data[key] = post_process_text(text)

        return extracted_data

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None


# Usage
pdf_path = '2024-06-10T2000/00_2005864_13.pdf'
result = cc_ocr(pdf_path, dpi=300)
if result:
    for key, value in result.items():
        print(f"{key}: {value}")
else:
    print("OCR processing failed.")
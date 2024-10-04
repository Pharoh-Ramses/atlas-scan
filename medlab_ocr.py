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


def medlab_ocr(pdf_path, dpi=300):
    try:
        images = convert_from_path(pdf_path, dpi=dpi)
        extracted_data = {}

        if len(images) > 0:
            processed_image = preprocess_image(images[0])

            regions = {
                'patient_name': (296, 472, 862, 529),
                'date_of_birth': (394, 526, 609, 575),
                'gender': (178, 571, 359, 628),
                'mrn': (380, 634, 656, 678),
                'test_name': (433, 1001, 1500, 1055),
                'specimen_type': (1199, 477, 1608, 527),
                'collection_date': (1198, 523, 1607, 577),
                'tested_pathogen': (175, 1123, 764, 1167),
                'test_result': (1295, 1119, 2087, 1172),
                'reported_date': (1192, 574, 1618, 627)
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
pdf_path = '2024-06-10T2000/2022_01_19__03_655974___Eloisa_Javier___1979_09_17_.pdf'
result = medlab_ocr(pdf_path, dpi=300)
if result:
    for key, value in result.items():
        print(f"{key}: {value}")
else:
    print("OCR processing failed.")
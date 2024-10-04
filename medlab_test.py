import os
import sys
from pdf2image import convert_from_path
import pytesseract
from PIL import Image, ImageDraw
import shutil


def medlab_ocr(pdf_path):
    # Convert PDF to image
    images = convert_from_path(pdf_path)

    extracted_data = {}

    # Process the page
    if len(images) > 0:
        # Extract patient information from specific regions
        extracted_data['patient_name'] = pytesseract.image_to_string(
            images[0].crop((292, 474, 590, 54)))  # example coordinates
        extracted_data['date_of_birth'] = pytesseract.image_to_string(
            images[0].crop((100, 140, 300, 170)))  # example coordinates
        extracted_data['gender'] = pytesseract.image_to_string(
            images[0].crop((100, 180, 300, 210)))  # example coordinates
        extracted_data['mrn'] = pytesseract.image_to_string(
            images[0].crop((100, 220, 300, 250)))  # example coordinates
        extracted_data['test_name'] = pytesseract.image_to_string(
            images[0].crop((100, 100, 500, 130)))  # example coordinates
        extracted_data['test_device'] = pytesseract.image_to_string(
            images[0].crop((100, 140, 500, 170)))  # example coordinates
        extracted_data['specimen_type'] = pytesseract.image_to_string(
            images[0].crop((100, 180, 500, 210)))  # example coordinates
        extracted_data['collection_date'] = pytesseract.image_to_string(
            images[0].crop((100, 220, 500, 250)))  # example coordinates
        extracted_data['tested_pathogen'] = pytesseract.image_to_string(
            images[0].crop((100, 260, 500, 290)))  # example coordinates
        extracted_data['test_result'] = pytesseract.image_to_string(
            images[0].crop((100, 300, 500, 330)))  # example coordinates
        extracted_data['reported_date'] = pytesseract.image_to_string(
            images[0].crop((100, 340, 500, 370)))  # example coordinates

    return extracted_data


def check_tesseract():
    if shutil.which('tesseract') is None:
        print("Tesseract is not installed or not in PATH.")
        print("Please install Tesseract OCR and ensure it's in your system PATH.")
        print("Installation guide: https://github.com/tesseract-ocr/tesseract")
        return False
    return True


def visualize_coordinates(image, coordinates, output_path):
    draw = ImageDraw.Draw(image)
    for field, coords in coordinates.items():
        draw.rectangle(coords, outline="red")
        draw.text((coords[0], coords[1] - 20), field, fill="red")
    image.save(output_path)
    print(f"Visualization saved to {output_path}")


def test_medlab_ocr_single_file(pdf_folder, pdf_filename):
    pdf_path = os.path.join(pdf_folder, pdf_filename)

    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return

    print(f"Processing: {pdf_filename}")

    if not check_tesseract():
        return

    try:
        extracted_data = medlab_ocr(pdf_path)

        print("Extracted Data:")
        for key, value in extracted_data.items():
            print(f"{key}: {value}")

        # Visualize the coordinates
        images = convert_from_path(pdf_path)
        if images:
            coordinates = {
                'patient_name': (100, 100, 300, 130),
                'date_of_birth': (100, 140, 300, 170),
                'gender': (100, 180, 300, 210),
                'mrn': (100, 220, 300, 250),
                'test_name': (100, 100, 500, 130),
                'test_device': (100, 140, 500, 170),
                'specimen_type': (100, 180, 500, 210),
                'collection_date': (100, 220, 500, 250),
                'tested_pathogen': (100, 260, 500, 290),
                'test_result': (100, 300, 500, 330),
                'reported_date': (100, 340, 500, 370)
            }
            output_path = os.path.join(pdf_folder, f"{pdf_filename}_visualization.png")
            visualize_coordinates(images[0], coordinates, output_path)

    except Exception as e:
        print(f"Error processing {pdf_filename}: {str(e)}")
        print("Traceback:")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_medlab_ocr.py <pdf_filename>")
        sys.exit(1)

    pdf_filename = sys.argv[1]
    pdf_folder = "2024-06-10T2000"  # Folder in the root of the project

    test_medlab_ocr_single_file(pdf_folder, pdf_filename)
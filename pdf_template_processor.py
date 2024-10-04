import os
import sys
import pytesseract
from pdf2image import convert_from_path
from PIL import Image, ImageOps, ImageEnhance
from medlab_ocr import medlab_ocr
from cc_ocr import cc_ocr
from db import get_db_connection, close_db_connection
from datetime import datetime
import psycopg2


def preprocess_image(image):
    gray_image = ImageOps.grayscale(image)
    enhancer = ImageEnhance.Contrast(gray_image)
    high_contrast = enhancer.enhance(2.0)
    threshold = 200
    binary_image = high_contrast.point(lambda p: p > threshold and 255)
    return binary_image


def determine_template(pdf_path, dpi=300):
    try:
        images = convert_from_path(pdf_path, dpi=dpi)
        if len(images) > 0:
            processed_image = preprocess_image(images[0])
            template_region = (1746, 68, 2465, 158)
            cropped = processed_image.crop(template_region)
            text = pytesseract.image_to_string(cropped).strip().upper()
            return "cc" if "MEDICAL RECORD" in text else "medlab"
    except Exception as e:
        print(f"An error occurred while determining the template: {str(e)}")
        return None


def process_pdf(pdf_path):
    template_type = determine_template(pdf_path)
    if template_type == "cc":
        print("Using CC OCR method")
        return cc_ocr(pdf_path), "cc"
    elif template_type == "medlab":
        print("Using MedLab OCR method")
        return medlab_ocr(pdf_path), "medlab"
    else:
        print("Could not determine template type")
        return None, None


def create_atlas_files_table(conn):
    try:
        cursor = conn.cursor()
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS atlas_files (
            id SERIAL PRIMARY KEY,
            patient_name TEXT,
            date_of_birth TEXT,
            gender TEXT,
            mrn TEXT,
            test_name TEXT,
            test_device TEXT,
            specimen_type TEXT,
            collection_date TEXT,
            tested_pathogen TEXT,
            test_result TEXT,
            reported_date TEXT,
            source TEXT
        )
        '''
        cursor.execute(create_table_query)
        conn.commit()
        print("Table 'atlas_files' created or updated successfully")
    except (Exception, psycopg2.Error) as error:
        print("Error creating or updating table:", error)


def save_to_database(conn, data, source):
    try:
        cursor = conn.cursor()
        insert_query = '''
        INSERT INTO atlas_files (patient_name, date_of_birth, gender, mrn, 
                                 test_name, test_device, specimen_type, 
                                 collection_date, tested_pathogen, test_result, 
                                 reported_date, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        cursor.execute(insert_query, (
            data.get('patient_name'),
            data.get('date_of_birth'),
            data.get('gender'),
            data.get('mrn'),
            data.get('test_name'),
            data.get('test_device'),
            data.get('specimen_type'),
            data.get('collection_date'),
            data.get('tested_pathogen'),
            data.get('test_result'),
            data.get('reported_date'),
            source
        ))
        conn.commit()
        print("Data saved to database")
    except (Exception, psycopg2.Error) as error:
        print(f"Error saving data to database: {str(error)}")


def create_checkpoint_table(conn):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processing_checkpoint
            (id SERIAL PRIMARY KEY, last_processed_file TEXT)
        ''')
        conn.commit()
    except (Exception, psycopg2.Error) as error:
        print(f"Error creating checkpoint table: {str(error)}")


def update_checkpoint(conn, filename):
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM processing_checkpoint')
        cursor.execute('INSERT INTO processing_checkpoint (last_processed_file) VALUES (%s)', (filename,))
        conn.commit()
    except (Exception, psycopg2.Error) as error:
        print(f"Error updating checkpoint: {str(error)}")


def get_last_processed_file(conn):
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT last_processed_file FROM processing_checkpoint')
        result = cursor.fetchone()
        return result[0] if result else None
    except (Exception, psycopg2.Error) as error:
        print(f"Error getting last processed file: {str(error)}")
        return None


def main(pdf_folder):
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to the database. Exiting.")
        return

    create_atlas_files_table(conn)
    create_checkpoint_table(conn)

    last_processed = get_last_processed_file(conn)
    resume_processing = False

    for filename in sorted(os.listdir(pdf_folder)):
        if not filename.endswith(".pdf"):
            continue

        if last_processed and not resume_processing:
            if filename == last_processed:
                resume_processing = True
            continue

        pdf_path = os.path.join(pdf_folder, filename)
        print(f"Processing: {filename}")

        result, source = process_pdf(pdf_path)

        if result and source:
            save_to_database(conn, result, source)
            update_checkpoint(conn, filename)
        else:
            print(f"OCR processing failed for {filename}")

        print("-" * 50)

    close_db_connection(conn)
    print("Processing completed.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python pdf_template_processor.py <pdf_folder>")
        sys.exit(1)

    pdf_folder = sys.argv[1]
    main(pdf_folder)
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
from tqdm import tqdm
from datetime import timedelta
import time
import logging

# Set up logging
logging.basicConfig(filename='pdf_processing.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')


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
    if not os.path.exists(pdf_path):
        logging.error(f"File not found: {pdf_path}")
        return None, None

    template_type = determine_template(pdf_path)
    if template_type == "cc":
        return cc_ocr(pdf_path), "cc"
    elif template_type == "medlab":
        return medlab_ocr(pdf_path), "medlab"
    else:
        logging.warning(f"Could not determine template type for {pdf_path}")
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
        logging.info(f"Data saved to database for {data.get('patient_name')}")
    except (Exception, psycopg2.Error) as error:
        logging.error(f"Error saving data to database: {str(error)}")


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

def reset_checkpoint(conn):
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM processing_checkpoint')
        conn.commit()
        print("Checkpoint reset for new folder processing")
    except (Exception, psycopg2.Error) as error:
        print(f"Error resetting checkpoint: {str(error)}")

def main(pdf_folder):
    if not os.path.exists(pdf_folder):
        logging.error(f"The specified folder does not exist - {pdf_folder}")
        return

    conn = get_db_connection()
    if not conn:
        logging.error("Failed to connect to the database. Exiting.")
        return

    create_atlas_files_table(conn)
    create_checkpoint_table(conn)
    
    last_processed = get_last_processed_file(conn)
    
    if last_processed:
        last_processed_folder = os.path.dirname(last_processed)
        if last_processed_folder != pdf_folder:
            logging.info(f"New folder detected. Resetting checkpoint.")
            reset_checkpoint(conn)
            last_processed = None

    pdf_files = [f for f in sorted(os.listdir(pdf_folder)) if f.endswith('.pdf')]
    
    if not pdf_files:
        logging.warning(f"No PDF files found in the folder: {pdf_folder}")
        close_db_connection(conn)
        return

    total_files = len(pdf_files)
    processed_files = 0
    cc_count = 0
    medlab_count = 0
    start_time = time.time()

    with tqdm(total=total_files, desc="Processing", unit="file", ncols=100) as pbar:
        for filename in pdf_files:
            if last_processed:
                if filename == os.path.basename(last_processed):
                    last_processed = None
                else:
                    processed_files += 1
                    pbar.update(1)
                    continue

            pdf_path = os.path.join(pdf_folder, filename)

            result, source = process_pdf(pdf_path)
            
            if result and source:
                save_to_database(conn, result, source)
                update_checkpoint(conn, os.path.join(pdf_folder, filename))
                if source == "cc":
                    cc_count += 1
                elif source == "medlab":
                    medlab_count += 1
            else:
                logging.warning(f"OCR processing failed for {filename}")
            
            processed_files += 1
            pbar.update(1)

            elapsed_time = time.time() - start_time
            files_left = total_files - processed_files
            if processed_files > 0:
                avg_time_per_file = elapsed_time / processed_files
                eta_seconds = avg_time_per_file * files_left
                eta = str(timedelta(seconds=int(eta_seconds)))
            else:
                eta = "Calculating..."

            pbar.set_description(f"CC: {cc_count} | MedLab: {medlab_count} | ETA: {eta}")

    close_db_connection(conn)
    logging.info("Processing completed.")
    logging.info(f"Total files processed: {total_files}")
    logging.info(f"CC files: {cc_count} | MedLab files: {medlab_count}")

    print("\nProcessing completed.")
    print(f"Total files processed: {total_files}")
    print(f"CC files: {cc_count} | MedLab files: {medlab_count}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python pdf_template_processor.py <pdf_folder>")
        sys.exit(1)

    pdf_folder = sys.argv[1]
    main(pdf_folder)

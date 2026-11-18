"""
Script Name: indexer.py

This script extracts text from a collection of Porsche 996 PDF manuals, 
cleans the text, and indexes it into a DuckDB database configured via config.yaml.
"""

import os
import yaml
import duckdb
import fitz  # PyMuPDF
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Update this path to your manual directory if needed
MANUAL_PATH = r"c:/Users/jwhow/Documents/Porsche/shop manual/"
OMIT_STRING = "www.WorkshopManuals.co.uk"

# List of PDFs to index
pdf_collection = [
    "00-996-General.pdf",
    "01-996-Diagnosis.pdf",
    "02-996-Diagnosis.pdf",
    "03-996-Engine.pdf",
    "04-996-Engine.pdf",
    "04-996-Fuel.pdf",
    "06-996-Transmission-Automatic.pdf",
    "07-996-Transmission-Manual.pdf",
    "08-996-Running-Gear.pdf",
    "09-996-Body.pdf",
    "10-996-Body-Exterior.pdf",
    "11-996-Body-Interior.pdf",
    "12-996-AC-Electrics.pdf",
    "13-996-Wiring.pdf"
]

def load_config(config_file: str = "config.yaml") -> Dict[str, Any]:
    """Loads configuration from a YAML file."""
    if not os.path.exists(MANUAL_PATH):
        raise FileNotFoundError(f"Configuration path not found: {MANUAL_PATH}")
    
    os.chdir(MANUAL_PATH)
    filepath = os.path.join(MANUAL_PATH, config_file)
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Config file not found at {filepath}. Please create it.")
        
    with open(filepath, 'r') as file:
        return yaml.safe_load(file)

def setup_database(conn):
    """Creates the DuckDB table for the index and clears old data if re-running."""
    logger.info("Setting up DuckDB schema...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS manual_index (
            filename VARCHAR,
            page_number INTEGER,
            content VARCHAR
        )
    ''')
    # Clear existing data to prevent duplicates if you run the indexer multiple times
    conn.execute('DELETE FROM manual_index')

def extract_and_index_pdf(filename: str, conn):
    """Extracts text from a PDF, cleans it, and inserts it into DuckDB."""
    if not os.path.exists(filename):
        logger.warning(f"Skipping: '{filename}' not found in the current directory.")
        return

    logger.info(f"Extracting and indexing: {filename}...")
    doc = fitz.open(filename)
    
    # We will collect all pages into a list of tuples to do a fast bulk insert
    bulk_data = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        
        # Omit the uninteresting URL watermark
        clean_text = text.replace(OMIT_STRING, "").strip()
        
        if clean_text:
            bulk_data.append((filename, page_num + 1, clean_text))
            
    doc.close()
    
    # Execute a bulk insert for high performance in DuckDB
    if bulk_data:
        conn.executemany('''
            INSERT INTO manual_index (filename, page_number, content)
            VALUES (?, ?, ?)
        ''', bulk_data)

if __name__ == "__main__":
    try:
        # 1. Load config and initialize DuckDB
        cfg = load_config()
        sql_cfg = cfg.get("sql", {})
        
        # Fallback to "manual_index.duckdb" if not explicitly set in config
        db_path = sql_cfg.get("database", "manual_index.duckdb")
        
        logger.info(f"Connecting to DuckDB database at: {db_path}")
        db_conn = duckdb.connect(database=db_path)
        
        # 2. Prepare the schema
        setup_database(db_conn)
        
        # 3. Index all files
        for pdf_file in pdf_collection:
            extract_and_index_pdf(pdf_file, db_conn)
            
        logger.info("Indexing complete! You can now launch the viewer GUI.")
        
    except Exception as e:
        logger.error(f"An error occurred during indexing: {e}")
    finally:
        if 'db_conn' in locals():
            db_conn.close()
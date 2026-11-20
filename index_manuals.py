"""
Script Name: index_manuals.py

This script extracts text from a collection of Porsche 996 PDF manuals,
cleans the text, and indexes it into a SQL database (DuckDB, SQLite, or SQL Server)
configured via global variables.
"""

import os
import fitz  # PyMuPDF
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# --- Global Configuration ---
MANUAL_PATH = r"."
OMIT_STRING = "www.WorkshopManuals.co.uk"

# Database settings: set DB_TYPE to "duckdb", "sqlite", or "odbc" (SQL Server)
DB_TYPE = "duckdb"
DB_DATABASE = "manual_index.duckdb"  # File path for DuckDB/SQLite, or DB name for SQL Server

# SQL Server (ODBC) settings — only used if DB_TYPE = "odbc"
DB_SERVER = "YOUR_SERVER_NAME"
DB_INSTANCE = ""
DB_PORT = "1433"
DB_DRIVER = "ODBC Driver 18 for SQL Server"
DB_TRUST_SERVER_CERTIFICATE = True

# List of PDFs to index
PDF_COLLECTION = [
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
    "13-996-Wiring.pdf",
]


# --- Database Connection Helpers ---

def _build_odbc_conn_str() -> str:
    """Builds the ODBC connection string for SQL Server connections."""
    server = DB_SERVER.strip()
    instance = DB_INSTANCE.strip()
    port = str(DB_PORT).strip()
    database = DB_DATABASE.strip()

    if not server or not database:
        raise ValueError("SQL config requires DB_SERVER and DB_DATABASE.")

    driver = DB_DRIVER.strip() or "ODBC Driver 18 for SQL Server"
    if not driver.startswith("{"):
        driver = "{" + driver
    if not driver.endswith("}"):
        driver = driver + "}"

    if instance:
        server_str = f"{server}\\{instance}"
    elif port:
        server_str = f"{server},{port}"
    else:
        server_str = server

    tsc = "yes" if DB_TRUST_SERVER_CERTIFICATE else "no"
    parts = [
        f"DRIVER={driver}",
        f"SERVER={server_str}",
        f"DATABASE={database}",
        "trusted_connection=yes",
        f"trustservercertificate={tsc}",
    ]

    return ";".join(parts) + ";"


def get_db_connection():
    """
    Returns a DB-API 2.0 compliant connection for DuckDB, SQLite, or SQL Server.
    """
    db_type = DB_TYPE.strip().lower()

    if db_type == "duckdb":
        import duckdb
        db_path = os.path.join(MANUAL_PATH, DB_DATABASE)
        return duckdb.connect(database=db_path)

    elif db_type == "sqlite":
        import sqlite3
        db_path = os.path.join(MANUAL_PATH, DB_DATABASE)
        return sqlite3.connect(db_path)

    elif db_type == "odbc":
        import pyodbc
        conn_str = _build_odbc_conn_str()
        return pyodbc.connect(conn_str)

    else:
        raise ValueError(f"Unsupported DB_TYPE: {db_type}. Use 'duckdb', 'sqlite', or 'odbc'.")


# --- Indexing Logic ---

def setup_database(conn):
    """Creates the manual_index table and clears old data if re-running."""
    db_type = DB_TYPE.strip().lower()
    cursor = conn.cursor()

    logger.info(f"Setting up schema for {db_type}...")

    if db_type == "odbc":
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='manual_index' AND xtype='U')
            BEGIN
                CREATE TABLE manual_index (
                    filename NVARCHAR(255),
                    page_number INT,
                    content NVARCHAR(MAX)
                )
            END
        ''')
    else:
        # Standard SQL compatible with DuckDB and SQLite
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS manual_index (
                filename VARCHAR,
                page_number INTEGER,
                content VARCHAR
            )
        ''')

    # Clear existing data to prevent duplicates on re-runs
    cursor.execute("DELETE FROM manual_index")
    conn.commit()


def extract_and_index_pdf(filename: str, conn):
    """Extracts text from a PDF, cleans it, and bulk-inserts it into the database."""
    pdf_path = os.path.join(MANUAL_PATH, filename)
    if not os.path.exists(pdf_path):
        logger.warning(f"Skipping: '{pdf_path}' not found.")
        return

    logger.info(f"Extracting and indexing: {filename}...")
    doc = fitz.open(pdf_path)
    bulk_data = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")

        # Omit the uninteresting URL watermark
        clean_text = text.replace(OMIT_STRING, "").strip()

        if clean_text:
            bulk_data.append((filename, page_num + 1, clean_text))

    doc.close()

    if bulk_data:
        cursor = conn.cursor()
        if DB_TYPE.strip().lower() == "odbc":
            cursor.fast_executemany = True
        cursor.executemany(
            "INSERT INTO manual_index (filename, page_number, content) VALUES (?, ?, ?)",
            bulk_data,
        )
        conn.commit()


if __name__ == "__main__":
    db_conn = None
    try:
        logger.info(f"Connecting to {DB_TYPE} database: {DB_DATABASE}")
        db_conn = get_db_connection()

        setup_database(db_conn)

        for pdf_file in PDF_COLLECTION:
            extract_and_index_pdf(pdf_file, db_conn)

        logger.info("Indexing complete! You can now launch manual_search.py.")

    except Exception as e:
        logger.error(f"An error occurred during indexing: {e}")
    finally:
        if db_conn:
            db_conn.close()
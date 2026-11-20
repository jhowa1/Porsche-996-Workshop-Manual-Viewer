# Porsche 996 Shop Manual Search & Viewer

A desktop application designed to index, search, and view PDF shop manuals for the Porsche 996. It features a split-pane graphical user interface built with PyQt6, PDF rendering via PyMuPDF, and case-insensitive, compound-word search capabilities provided by a SQL database.

## Assumptions & Design Principles
* **Single Directory Structure:** To keep the application as simple as possible, it is assumed that all files—including the Python scripts, the local database file, and the PDF manuals—reside in the same directory.
* **Manual Names are Not Changed:** It is assumed that all of the PDF manual names are not modified.
* **Database Agnostic:** The application defaults to using DuckDB for a zero-configuration, portable experience, but has been fully tested on SQL Server. The underlying architecture is intended to be database-agnostic, allowing you to choose your preferred SQL backend via global variables at the top of the Python scripts.

## Features

* **Case-Insensitive Multi-Word Search:** Enter multiple keywords in any case (e.g., "Remove Console") to find pages containing all words, even if they aren't right next to each other (e.g., "remove center console").
* **Context Snippets:** The search results display a snippet showing 3 words before and 15 words after your search terms to give you instant context.
* **Integrated PDF Viewer:** Click any search result to instantly render the corresponding PDF page in the viewer.
* **Page Navigation:** Use the on-screen buttons or keyboard arrows (Left/Right) to flip through pages of the manual.
* **Print Support:** Print the currently displayed page with a single click or by pressing `Ctrl+P`.
* **Database Agnostic:** Seamlessly switch between DuckDB (default, zero-setup), SQLite, or SQL Server via global configuration variables—no external config file required.

## Getting Started from Scratch

Follow these steps to set up your Python environment, index your PDF manuals, and launch the viewer.

### Step 1: Initial Setup

1. **Install Python:** Ensure Python 3.8 or newer is installed on your system.
2. **Install Required Libraries:** 
   Run the following pip command to install all necessary dependencies for the GUI, PDF rendering, and database connections:
   ```bash
   pip install PyQt6 PyMuPDF duckdb pyodbc
   ```
   *(Note: `pyodbc` is only required if you plan to use SQL Server.)*
3. **Extract the Manuals to a Directory:** 
   You can download both factory manuals from here: https://audipages.com/911/wsm/
   The zip file 996_MK1_WSM.zip	contains all of the manuals.  Create a folder to host the manuals.
   The folder containing all of the manuals is the same directory where the Python scripts will be placed. 

### Step 2: Configure the Database (Global Variables)

Database settings are defined using global variables near the top of `manual_search.py` (and `index_manuals.py`), eliminating the need for an external configuration file. Edit these variables to match your preferred database.   The code assumes Option A is chosen and has placed these variables in the Python scripts of this app.

**Option A: DuckDB (Default — Recommended for portability, no server required)**
```python
MANUAL_PATH = r"."
DB_TYPE = "duckdb"
DB_DATABASE = "manual_index.duckdb"
```

**Option B: SQL Server (Windows Authentication)**
```python
MANUAL_PATH = r"."
DB_TYPE = "odbc"
DB_DATABASE = "YOUR_DATABASE_NAME"

DB_SERVER = "YOUR_SERVER_NAME"
DB_INSTANCE = ""  # Add your instance name if applicable, otherwise leave blank
DB_PORT = "1433"
DB_DRIVER = "ODBC Driver 18 for SQL Server"
DB_TRUST_SERVER_CERTIFICATE = True
```

### Step 3: Index the PDF Manuals (`index_manuals.py`)

Before searching, run the manual extract script: `index_manuals.py`. This script populates the database with text from the collection of PDF manuals. Once this is done, there is no need to run it again.

**What it does:**
* Uses PyMuPDF to read every page of the provided PDF files.
* Cleans the extracted text by stripping out unneeded watermarks (like website URLs).
* Connects to your configured database and performs a high-speed bulk insert to populate the `manual_index` table.

Run the indexing script once from your terminal/command prompt:
```bash
python index_manuals.py
```

### Step 4: Run the Application (`manual_search.py`)

The `manual_search.py` script contains the main user interface. To make invoking the script super easy on Windows, create a simple launcher file in the same directory:

**For Windows (Create `Launch_Manuals.bat`):**
```bat
@echo off
echo Starting Porsche 996 Manual Viewer...
python manual_search.py
exit
```

Simply double-click your launcher file to open the search GUI, view your diagrams, and print pages!

**For Linux / Mac:**
This application has been tested on Ubuntu. Due to variations between Linux and Mac, the user is invited to customize how the scripts are launched to meet their requirements.

## Keyboard Shortcuts

* **`Ctrl + P`**: Print the currently visible page.
* **`Left Arrow`**: Go to the previous page in the current PDF.
* **`Right Arrow`**: Go to the next page in the current PDF.
* **`Enter` (in search box)**: Execute the search.

## Troubleshooting

* **File Not Found:** Ensure that `MANUAL_PATH` at the top of `manual_search.py` matches the folder where your PDFs and database live (default is `"."`, the current directory). Use forward slashes `/` if specifying a full path.
* **No Search Results:** Ensure you have successfully run the indexing script (`index_manuals.py`) first. If using DuckDB, the `manual_index.duckdb` file should exist in your folder and have a file size greater than 0 KB.
* **ODBC Errors:** If you switch `DB_TYPE` from `"duckdb"` to `"odbc"`, ensure you have the Microsoft ODBC Driver 18 for SQL Server installed on your machine.
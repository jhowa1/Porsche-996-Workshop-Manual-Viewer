# Porsche 996 Shop Manual Search & Viewer

A desktop application designed to index, search, and view PDF shop manuals for the Porsche 996. It features a split-pane graphical user interface built with PyQt6, PDF rendering via PyMuPDF, and compound-word search capabilities provided by a SQL database.

## Assumptions & Design Principles
* **Single Directory Structure:** To keep the application as simple as possible, it is assumed that all files—including the Python scripts, `config.yaml`, and the PDF manuals—reside in the same directory.
* **Manual Names are Not Changed:** It is assumed that all of the PDF manual names are not modified.
* **Database Agnostic:** The application defaults to using DuckDB for a zero-configuration, portable experience, but has been fully tested on SQL Server. The underlying architecture is intended to be database-agnostic, allowing you to choose your preferred SQL backend via the configuration file.

## Features

* **Multi-Word Search:** Enter multiple keywords (e.g., "remove center console") to find pages containing all words, even if they aren't right next to each other.
* **Context Snippets:** The search results display a snippet showing 3 words before and 15 words after your search terms to give you instant context.
* **Integrated PDF Viewer:** Click any search result to instantly render the corresponding PDF page in the viewer.
* **Page Navigation:** Use the on-screen buttons or keyboard arrows (Left/Right) to flip through pages of the manual.
* **Print Support:** Print the currently displayed page with a single click or by pressing `Ctrl+P`.
* **Database Agnostic:** Seamlessly switch between DuckDB (default, zero-setup), SQLite, or SQL Server via a simple YAML configuration.

## Getting Started from Scratch

Follow these steps to set up your Python environment, index your PDF manuals, and launch the viewer.

### Step 1: Initial Setup

1. **Install Python:** Ensure Python 3.8 or newer is installed on your system.
2. **Install Required Libraries:** 
   Run the following pip command to install all necessary dependencies for the GUI, PDF rendering, and database connections:
   ```bash
   pip install PyQt6 pyodbc PyMuPDF pyyaml duckdb
   ```
3. **Extract the Manuals to a Directory:** 
   All manuals and code will exist in the same directory. 

### Step 2: Configure the Database (`config.yaml`)

Create a file named `config.yaml` in your manual directory by downloading one of the following templates for your preferred database. If you download the template from GitHub ensure the names is `config.yaml`

**Option A: DuckDB (Recommended for portability, no server required)**
```yaml
sql:
  type: "duckdb"
  database: "manual_index.duckdb"
```

**Option B: SQL Server (Windows Authentication)**
```yaml
sql:
  type: "odbc"
  driver: "ODBC Driver 18 for SQL Server"
  server: "YOUR_SERVER_NAME"
  instance: ""                  # Add your instance name if applicable, otherwise leave blank
  port: 1433
  database: "YOUR_DATABASE_NAME"
  integrated_security: true
  encrypt: true
  trust_server_certificate: true
```

### Step 3: Index the PDF Manuals (`index_manuals.py`)

Before searching, run the manual extract script: `index_manuals.py`.   This script populates the database with text from the collection of PDF manuals.  Once this is done, there is no need to run it again.

**What it does:**
* Uses PyMuPDF to read every page of the provided PDF files.
* Cleans the extracted text by stripping out unneeded watermarks (like website URLs).
* Connects to your configured database (via `config.yaml`) and performs a high-speed bulk insert to populate the `manual_index` table.

Run the indexing script once from your terminal/command prompt:
```bash
python index_manuals.py
```

### Step 4: Run the Application (`search_viewer_gui.py`)

The `search_viewer_gui.py` script contains the main user interface. To make invoking the script super easy, create a simple launcher file in the same directory:

**For Windows (Create `Launch_Manuals.bat`):**
```bat
@echo off
echo Starting Porsche 996 Manual Viewer...
python search_viewer_gui.py
exit
```

**For Mac/Linux (Create `launch_manuals.sh`):**
```bash
#!/bin/bash
echo "Starting Porsche 996 Manual Viewer..."
python3 search_viewer_gui.py
```
*(Remember to run `chmod +x launch_manuals.sh` to make it executable).*

Simply double-click your launcher file to open the search GUI, view your diagrams, and print pages!

## Keyboard Shortcuts

* **`Ctrl + P`**: Print the currently visible page.
* **`Left Arrow`**: Go to the previous page in the current PDF.
* **`Right Arrow`**: Go to the next page in the current PDF.
* **`Enter` (in search box)**: Execute the search.

## Troubleshooting

* **File Not Found / Config Missing:** Ensure that the `MANUAL_PATH` hardcoded at the top of the Python script exactly matches the folder where your PDFs and `config.yaml` live. Use forward slashes `/` in the path.
* **No Search Results:** Ensure you have successfully run the indexing script first. If using DuckDB, the `manual_index.duckdb` file should exist in your folder and have a file size greater than 0 KB.
* **ODBC Errors:** If you switch `type` in the config from `duckdb` to `odbc`, ensure you have the Microsoft ODBC Driver 18 for SQL Server installed on your machine.
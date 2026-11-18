"""
Script Name: search_viewer_gui.py

This module provides a graphical user interface (GUI) to search a database index 
of PDF manuals, display specific pages, navigate pages, and print them. It uses a 
config.yaml file for database connection settings and supports DuckDB, SQLite, and SQL Server.
"""

import sys
import os
import re
import yaml
import fitz  # PyMuPDF
import logging
import traceback
from typing import Dict, Any, Optional

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QLabel,
    QScrollArea, QSplitter, QMessageBox, QAbstractItemView, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage, QPainter, QKeySequence, QShortcut
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

# Setup logging for the connection builder
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MANUAL_PATH = r"c:/Users/jwhow/Documents/Porsche/shop manual/"

# --- Database Connection Helpers ---

def load_config(config_file: str = "config.yaml") -> Dict[str, Any]:
    if not os.path.exists(MANUAL_PATH):
        raise FileNotFoundError(f"Configuration file not found: {MANUAL_PATH}")
    
    os.chdir(MANUAL_PATH)
    filepath = os.path.join(MANUAL_PATH, config_file)
    with open(filepath, 'r') as file:
        return yaml.safe_load(file)

def _build_odbc_conn_str(sql_cfg: Dict[str, Any]) -> str:
    """Builds the ODBC connection string for SQL Server connections."""
    server = (sql_cfg.get("server") or sql_cfg.get("host") or "").strip()
    instance = (sql_cfg.get("instance") or "").strip()
    port = str(sql_cfg.get("port") or "").strip()
    database = (
        sql_cfg.get("database") or sql_cfg.get("db") or sql_cfg.get("dbname") or ""
    ).strip()

    if not server or not database:
        raise ValueError("SQL config requires 'server' and 'database'.")

    driver = sql_cfg.get("driver") or sql_cfg.get("odbc_driver") or "ODBC Driver 18 for SQL Server"
    
    if not driver.startswith("{"):
        driver = "{" + driver
    if not driver.endswith("}"):
        driver = driver + "}"

    if instance:
        server_str = "%s\\%s" % (server, instance)
    elif port:
        server_str = "%s,%s" % (server, port)
    else:
        server_str = server

    parts = [
        "DRIVER=%s" % driver,
        "SERVER=%s" % server_str,
        "DATABASE=%s" % database,
        "trusted_connection=yes",
    ]

    tsc = sql_cfg.get("trust_server_certificate", True)
    parts.append(
        "trustservercertificate=%s"
        % ("yes" if str(tsc).lower() in ("1", "true", "yes", "y", "on") else "no")
    )

    conn_str = ";".join(parts) + ";"
    logger.debug("ODBC conn str (trusted): %s", conn_str)
    return conn_str

def get_db_connection(config: Optional[Dict[str, Any]] = None):
    """
    Factory function to return a DB-API 2.0 compliant connection.
    Supports duckdb, sqlite, and odbc (SQL Server) based on config.yaml.
    """
    cfg = config or load_config("config.yaml")
    sql_cfg = cfg.get("sql") or {}
    
    db_type = sql_cfg.get("type", "odbc").lower()
    
    if db_type == "duckdb":
        import duckdb
        db_path = sql_cfg.get("database", "manual_index.duckdb")
        return duckdb.connect(database=db_path)
        
    elif db_type == "sqlite":
        import sqlite3
        db_path = sql_cfg.get("database", "manual_index.db")
        return sqlite3.connect(db_path)
        
    elif db_type == "odbc":
        import pyodbc
        conn_str = _build_odbc_conn_str(sql_cfg)
        return pyodbc.connect(conn_str)
        
    else:
        raise ValueError(f"Unsupported database type: {db_type}. Use 'duckdb', 'sqlite', or 'odbc'.")


# --- GUI Application ---

class ManualSearchViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Porsche 996 Manual Search & Viewer")
        self.resize(1400, 900)

        self.conn = None
        self.cursor = None
        self.current_pixmap = None
        
        # State tracking for navigation
        self.current_pdf_path = None
        self.current_page_num = -1
        self.total_pages = 0

        self.init_ui()
        self.connect_db()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- LEFT PANEL: Image/PDF Viewer ---
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(False)
        self.image_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.image_label = QLabel("Search for a term and select a page to view.")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_scroll.setWidget(self.image_label)

        # --- RIGHT PANEL: Controls and Results ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Search Box
        search_layout = QHBoxLayout()
        search_lbl = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("e.g. spark plugs, torque...")
        self.search_input.returnPressed.connect(self.execute_search)

        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self.execute_search)

        search_layout.addWidget(search_lbl)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.btn_search)
        right_layout.addLayout(search_layout)

        # Results Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Manual File", "Page", "Snippet"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellClicked.connect(self.load_selected_page)
        right_layout.addWidget(self.table)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_prev = QPushButton("<< Prev Page")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_prev.setEnabled(False)

        self.btn_next = QPushButton("Next Page >>")
        self.btn_next.clicked.connect(self.next_page)
        self.btn_next.setEnabled(False)
        
        self.btn_print = QPushButton("Print (Ctrl+P)")
        self.btn_print.clicked.connect(self.print_page)
        self.btn_print.setEnabled(False)

        self.btn_exit = QPushButton("Exit")
        self.btn_exit.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_prev)
        btn_layout.addWidget(self.btn_next)
        btn_layout.addWidget(self.btn_print)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_exit)
        right_layout.addLayout(btn_layout)

        splitter.addWidget(self.image_scroll)
        splitter.addWidget(right_panel)
        splitter.setSizes([700, 700])

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(self.print_page)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self).activated.connect(self.prev_page)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self).activated.connect(self.next_page)

    def connect_db(self):
        try:
            self.conn = get_db_connection()
            self.cursor = self.conn.cursor()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not connect to Database:\n{str(e)}")

    def execute_search(self):
        import re

        if not self.cursor:
            return

        query = self.search_input.text().strip()
        if not query:
            return

        try:
            self.table.setRowCount(0)
            
            # Split the query into individual words for compound searching
            search_words = query.split()
            
            # Build dynamic SQL with an AND condition for each word
            like_clauses = " AND ".join(["content LIKE ?"] * len(search_words))
            sql = f'''
                SELECT filename, page_number, content 
                FROM manual_index 
                WHERE {like_clauses}
            '''
            
            # Create the parameter tuple
            params = tuple(f"%{word}%" for word in search_words)
            
            self.cursor.execute(sql, params)
            rows = self.cursor.fetchall()
            
            # Build a regex pattern to find the first occurrence of ANY of the search words
            escaped_words = [re.escape(w) for w in search_words]
            words_or_pattern = "|".join(escaped_words)
            pattern = re.compile(rf'((?:\S+\s+){{0,3}})({words_or_pattern})((?:\s+\S+){{0,15}})', re.IGNORECASE)
            
            for row_idx, row_data in enumerate(rows):
                self.table.insertRow(row_idx)
                self.table.setItem(row_idx, 0, QTableWidgetItem(str(row_data[0])))
                self.table.setItem(row_idx, 1, QTableWidgetItem(str(row_data[1])))
                
                full_text = str(row_data[2]).replace('\n', ' ')
                
                # Extract the targeted snippet around the first matched word
                match = pattern.search(full_text)
                if match:
                    snippet = "".join(match.groups()).strip()
                else:
                    snippet = " ".join(search_words) 
                
                self.table.setItem(row_idx, 2, QTableWidgetItem(f"... {snippet} ..."))

            if not rows:
                QMessageBox.information(self, "No Results", f"No matches found for '{query}'.")

        except Exception as e:
            QMessageBox.critical(self, "Search Error", str(e))

    def load_selected_page(self, row, col):
        filename_item = self.table.item(row, 0)
        page_item = self.table.item(row, 1)

        if not filename_item or not page_item:
            return

        self.current_pdf_path = os.path.join(MANUAL_PATH, filename_item.text())
        self.current_page_num = int(page_item.text()) - 1 
        
        self.render_current_page()

    def prev_page(self):
        if self.current_page_num > 0:
            self.current_page_num -= 1
            self.render_current_page()

    def next_page(self):
        if self.current_page_num < self.total_pages - 1:
            self.current_page_num += 1
            self.render_current_page()

    def render_current_page(self):
        if not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            QMessageBox.warning(self, "File Not Found", f"Could not locate PDF:\n{self.current_pdf_path}")
            return

        try:
            doc = fitz.open(self.current_pdf_path)
            self.total_pages = len(doc)
            
            if self.current_page_num < 0 or self.current_page_num >= self.total_pages:
                doc.close()
                return

            page = doc.load_page(self.current_page_num)
            
            zoom = 2.0 
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            self.current_pixmap = QPixmap.fromImage(qimg.copy())

            self.image_label.setPixmap(self.current_pixmap)
            self.image_label.setMinimumSize(self.current_pixmap.size())
            self.image_label.resize(self.current_pixmap.size())
            self.image_label.adjustSize()
            
            # Update button states
            self.btn_print.setEnabled(True)
            self.btn_prev.setEnabled(self.current_page_num > 0)
            self.btn_next.setEnabled(self.current_page_num < self.total_pages - 1)
            
            doc.close()

        except Exception as e:
            QMessageBox.critical(self, "Render Error", f"Error loading PDF page:\n{e}")

    def print_page(self):
        if not self.current_pixmap:
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)

        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            try:
                painter = QPainter(printer)
                rect = painter.viewport()
                size = self.current_pixmap.size()
                size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
                painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
                painter.setWindow(self.current_pixmap.rect())
                painter.drawPixmap(0, 0, self.current_pixmap)
                painter.end()
            except Exception as e:
                QMessageBox.critical(self, "Print Error", f"Failed to print:\n{e}")

    def closeEvent(self, event):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
        event.accept()

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        window = ManualSearchViewer()
        window.show()
        sys.exit(app.exec())
    except SystemExit:
        pass
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    main()
# Windows test version of matrix.py
# This version mocks hardware and uses Windows-compatible paths

from datetime import datetime
import os, errno
import time
import io, re
import sqlite3
import subprocess
import atexit
import matrixux
from PyQt5.QtCore import QThread
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtCore import QTimer,QDateTime
import socket
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import json
import sys

# New validation modules
try:
    from duplicate_tracker import DuplicateTracker
    from logic import handle_qr_scan
except Exception as _e:
    DuplicateTracker = None
    def handle_qr_scan(qr_code, batch_line, mould_ranges, duplicate_checker=None):
        return "OUT OF BATCH", None

import getpass
import threading
import mmap

# Windows paths
SCANNER_PATH = os.path.dirname(os.path.abspath(__file__))
LOCATION_JSON = os.path.join(SCANNER_PATH, "location.json")
DB_PATH = os.path.join(SCANNER_PATH, "scanner.db")
CAT_FILE = os.path.join(SCANNER_PATH, "cat")
MATRIX_FILE = os.path.join(SCANNER_PATH, "matrix.txt")
ACC_CSV = os.path.join(SCANNER_PATH, "Acc.csv")
REJ_CSV = os.path.join(SCANNER_PATH, "Rej.csv")
BATCH_LOGS = os.path.join(SCANNER_PATH, "Batch_Setup_Logs")

mutex_wrkrbusy = threading.Lock()

cube="NA"
line="NA"
batch_number = ""
_mould_ranges = {}
user="NA"
trigger=False
inscanner=False  # Disable scanner on Windows
global text
text='--'
synch_serialthread=1

def get_ip_address(ifname):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setblocking(0)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception as e:
        return "127.0.0.1"

def loadsettings():
    global line, cube, trigger, inscanner, batch_number
    try:
        with open(LOCATION_JSON, "r") as jason_in:
            data = json.load(jason_in)
            cube = data['cube']
            line = data['line']
            trigger = (data.get('trigger', '0') == '1')
            inscanner = False  # Always false on Windows
            batch_number = data.get('batch_number', '').strip().upper() if isinstance(data, dict) else ""
    except Exception as e:
        print(f"Error loading settings: {e}")
        # Defaults
        cube = "1"
        line = "A"
        trigger = False
        inscanner = False
        batch_number = ""

def _load_mould_ranges(batch_no: str, line_letter: str):
    ranges = {}
    import csv
    candidates = []
    if batch_no:
        candidates.append(os.path.join(BATCH_LOGS, f"{batch_no}_setup.csv"))
        candidates.append(os.path.join(SCANNER_PATH, f"{batch_no}_setup.csv"))
    candidates.append(os.path.join(SCANNER_PATH, "batch_setup.csv"))
    
    for path in candidates:
        try:
            if os.path.exists(path):
                with open(path, 'r', newline='') as fh:
                    reader = csv.reader(fh)
                    header = next(reader, None)
                    for row in reader:
                        try:
                            bno, ln, mould, start, end = row[0].strip().upper(), row[1].strip().upper(), row[2].strip().upper(), row[3].strip().upper(), row[4].strip().upper()
                        except Exception:
                            continue
                        if line_letter and ln and ln != line_letter:
                            continue
                        if mould and start and end:
                            ranges[mould] = (start, end)
                if ranges:
                    return ranges
        except Exception:
            pass
    
    try:
        jpath = os.path.join(SCANNER_PATH, "batch_setup.json")
        if os.path.exists(jpath):
            with open(jpath, 'r') as fh:
                data = json.load(fh)
                if isinstance(data, dict):
                    for mould, val in data.items():
                        if isinstance(val, dict):
                            start = str(val.get('start', '')).strip().upper()
                            end = str(val.get('end', '')).strip().upper()
                            if mould and start and end:
                                ranges[mould.strip().upper()] = (start, end)
    except Exception:
        pass
    return ranges

# Batch Setup dialog
class BatchSetupDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Setup")
        self.setModal(True)
        self.resize(600, 420)

        vbox = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        vbox.addLayout(form)

        self.batch_edit = QtWidgets.QLineEdit(self)
        self.line_edit = QtWidgets.QLineEdit(self)
        self.mould_count = QtWidgets.QSpinBox(self)
        self.mould_count.setRange(1, 64)
        self.mould_count.valueChanged.connect(self._rows_changed)

        try:
            self.batch_edit.setText(batch_number)
            self.line_edit.setText(line)
        except Exception:
            pass

        form.addRow("Batch Number", self.batch_edit)
        form.addRow("Line", self.line_edit)
        form.addRow("Number of moulds", self.mould_count)

        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["MouldType", "QR_Start", "QR_End"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        vbox.addWidget(self.table)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel, self)
        btns.accepted.connect(self._save_and_close)
        btns.rejected.connect(self.reject)
        vbox.addWidget(btns)

        self._populate_from_existing()

    def _populate_from_existing(self):
        try:
            existing = list(_mould_ranges.items()) if isinstance(_mould_ranges, dict) else []
            count = max(1, len(existing))
            self.mould_count.setValue(count)
            self.table.setRowCount(count)
            for r in range(count):
                mould = existing[r][0] if r < len(existing) else ""
                start = existing[r][1][0] if r < len(existing) else ""
                end = existing[r][1][1] if r < len(existing) else ""
                self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(mould))
                self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(start))
                self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(end))
        except Exception as e:
            print(e)

    def _rows_changed(self, n):
        self.table.setRowCount(n)
        for r in range(n):
            for c in range(3):
                if not self.table.item(r, c):
                    self.table.setItem(r, c, QtWidgets.QTableWidgetItem(""))

    def _save_and_close(self):
        try:
            bn = self.batch_edit.text().strip().upper()
            ln = self.line_edit.text().strip().upper()
            if not bn or not ln:
                QtWidgets.QMessageBox.warning(self, "Missing data", "Please enter Batch Number and Line")
                return
            rows = self.table.rowCount()
            entries = []
            for r in range(rows):
                mould_item = self.table.item(r, 0)
                start_item = self.table.item(r, 1)
                end_item = self.table.item(r, 2)
                mould = (mould_item.text().strip().upper() if mould_item else "")
                start = (start_item.text().strip().upper() if start_item else "")
                end = (end_item.text().strip().upper() if end_item else "")
                if mould and start and end:
                    entries.append((mould, start, end))
            if not entries:
                QtWidgets.QMessageBox.warning(self, "No moulds", "Please enter at least one mould with start/end")
                return

            import csv
            os.makedirs(BATCH_LOGS, exist_ok=True)
            csv_path = os.path.join(BATCH_LOGS, f"{bn}_setup.csv")
            with open(csv_path, "w", newline="") as fh:
                wr = csv.writer(fh)
                wr.writerow(["BatchNo", "Line", "MouldType", "QR_Start", "QR_End"])
                for mould, start, end in entries:
                    wr.writerow([bn, ln, mould, start, end])

            try:
                with open(LOCATION_JSON, 'r+') as jf:
                    data = json.load(jf)
                    data['batch_number'] = bn
                    data['line'] = ln
                    jf.seek(0)
                    json.dump(data, jf, indent=2)
                    jf.truncate()
            except Exception as e:
                print(e)

            global batch_number, line, _mould_ranges
            batch_number = bn
            line = ln
            _mould_ranges = _load_mould_ranges(batch_number, line)

            QtWidgets.QMessageBox.information(self, "Saved", f"Batch setup saved to:\n{csv_path}")
            self.accept()
        except Exception as e:
            print(e)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save: {e}")

# Settings window (simplified for Windows)
class Window2(QMainWindow):
    def __init__(self):
        super(Window2, self).__init__()
        self.setWindowTitle("Settings")
        self.resize(500, 400)
        
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        
        form = QtWidgets.QFormLayout()
        
        self.line_edit = QtWidgets.QLineEdit(line)
        self.cube_edit = QtWidgets.QLineEdit(cube)
        self.batch_edit = QtWidgets.QLineEdit(batch_number)
        
        form.addRow("Line:", self.line_edit)
        form.addRow("Cube:", self.cube_edit)
        form.addRow("Batch Number:", self.batch_edit)
        
        layout.addLayout(form)
        
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.batch_setup_btn = QtWidgets.QPushButton("Batch Setup...")
        self.batch_setup_btn.clicked.connect(self.open_batch_setup)
        
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.clicked.connect(self.save_clicked)
        
        self.close_btn = QtWidgets.QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        
        btn_layout.addWidget(self.batch_setup_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
        
    def open_batch_setup(self):
        try:
            dlg = BatchSetupDialog(self)
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                loadsettings()
                global _mould_ranges
                _mould_ranges = _load_mould_ranges(batch_number, line)
        except Exception as e:
            print(e)
            
    def save_clicked(self):
        global line, cube, batch_number
        try:
            with open(LOCATION_JSON, 'r+') as outfile:
                data = json.load(outfile)
                data["line"] = self.line_edit.text().strip().upper()
                data["cube"] = self.cube_edit.text().strip()
                data["batch_number"] = self.batch_edit.text().strip().upper()
                outfile.seek(0)
                json.dump(data, outfile, indent=2)
                outfile.truncate()
            loadsettings()
            QtWidgets.QMessageBox.information(self, "Saved", "Settings saved successfully!")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save: {e}")

# Simplified main window for Windows testing
class matrix_gui(QtWidgets.QMainWindow):
    def __init__(self):
        try:
            print("matrix_gui.__init__ starting...")
            super(matrix_gui, self).__init__()
            self.setWindowTitle("SCANNER Test - Windows")
            self.resize(800, 600)
            
            central = QtWidgets.QWidget()
            self.setCentralWidget(central)
            layout = QtWidgets.QVBoxLayout(central)
            
            print("Loading settings...")
            loadsettings()
            print(f"Settings loaded: line={line}, cube={cube}, batch_number={batch_number}")
            
            # Info display
            info = QtWidgets.QTextEdit()
            info.setReadOnly(True)
            info.setHtml(f"""
            <h2>SCANNER - Windows Test Mode</h2>
            <p><b>Line:</b> {line}<br>
            <b>Cube:</b> {cube}<br>
            <b>Batch:</b> {batch_number or '(not set)'}<br>
            <b>User:</b> {getpass.getuser()}<br>
            <b>Time:</b> {datetime.now().strftime("%I:%M %p")}</p>
            <hr>
            <p><b>Status:</b> UI test mode - hardware functions disabled</p>
            """)
            layout.addWidget(info)
            
            # QR input
            qr_layout = QtWidgets.QHBoxLayout()
            qr_layout.addWidget(QtWidgets.QLabel("Test QR Code:"))
            self.qr_input = QtWidgets.QLineEdit()
            self.qr_input.setPlaceholderText("Enter QR code to test validation...")
            self.qr_input.returnPressed.connect(self.test_qr)
            qr_layout.addWidget(self.qr_input)
            layout.addLayout(qr_layout)
            
            # Result display
            self.result_display = QtWidgets.QTextEdit()
            self.result_display.setReadOnly(True)
            self.result_display.setMaximumHeight(150)
            layout.addWidget(self.result_display)
            
            # Buttons
            btn_layout = QtWidgets.QHBoxLayout()
            
            settings_btn = QtWidgets.QPushButton("Settings")
            settings_btn.clicked.connect(self.open_settings)
            
            reload_btn = QtWidgets.QPushButton("Reload Ranges")
            reload_btn.clicked.connect(self.reload_ranges)
            
            quit_btn = QtWidgets.QPushButton("Quit")
            quit_btn.clicked.connect(self.close)
            
            btn_layout.addWidget(settings_btn)
            btn_layout.addWidget(reload_btn)
            btn_layout.addWidget(quit_btn)
            
            layout.addLayout(btn_layout)
            
            # Load mould ranges
            global _mould_ranges
            _mould_ranges = _load_mould_ranges(batch_number, line)
            print(f"Mould ranges loaded: {len(_mould_ranges)} moulds")
            
            if _mould_ranges:
                info.append(f"\n<b>Loaded {len(_mould_ranges)} mould(s):</b><br>")
                for mould, (start, end) in _mould_ranges.items():
                    info.append(f"• {mould}: {start} → {end}<br>")
            else:
                info.append("\n<b style='color:orange;'>No mould ranges loaded. Use Settings → Batch Setup to configure.</b>")
            
            print("matrix_gui initialization complete!")
            
        except Exception as e:
            print(f"!!! Exception in matrix_gui.__init__: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def test_qr(self):
        qr = self.qr_input.text().strip().upper()
        if not qr:
            return
        
        try:
            status, mould = handle_qr_scan(qr, line, _mould_ranges, duplicate_checker=None)
            
            color = "green" if status == "PASS" else "red" if status in ["INVALID FORMAT", "LINE MISMATCH", "OUT OF BATCH"] else "orange"
            
            result_html = f"""
            <div style='background-color:{color};color:white;padding:10px;margin:5px 0;'>
            <b>QR:</b> {qr}<br>
            <b>Status:</b> {status}<br>
            <b>Mould:</b> {mould or 'N/A'}
            </div>
            """
            self.result_display.append(result_html)
            self.qr_input.clear()
            
        except Exception as e:
            self.result_display.append(f"<div style='background-color:red;color:white;padding:10px;'>ERROR: {e}</div>")
    
    def open_settings(self):
        w = Window2()
        w.exec_()
        # Refresh after settings close
        loadsettings()
        global _mould_ranges
        _mould_ranges = _load_mould_ranges(batch_number, line)
    
    def reload_ranges(self):
        global _mould_ranges
        _mould_ranges = _load_mould_ranges(batch_number, line)
        QtWidgets.QMessageBox.information(self, "Reloaded", f"Loaded {len(_mould_ranges)} mould range(s)")

if __name__ == "__main__":
    print("=== SCANNER App Starting (Windows Test Mode) ===")
    print(f"Python: {sys.version}")
    print(f"Working directory: {SCANNER_PATH}")
    
    # Ensure required files exist
    if not os.path.exists(LOCATION_JSON):
        print("Creating default location.json...")
        with open(LOCATION_JSON, 'w') as f:
            json.dump({"line": "A", "cube": "1", "trigger": "0", "scanner": "1", "batch_number": ""}, f, indent=2)
    
    os.makedirs(BATCH_LOGS, exist_ok=True)
    
    try:
        app = QtWidgets.QApplication(sys.argv)
        print("QApplication created: OK")
        
        MainWindow = matrix_gui()
        print("MainWindow created: OK")
        
        MainWindow.show()
        print("MainWindow shown: OK")
        print("=== Starting Qt event loop ===")
        
        sys.exit(app.exec_())
    except Exception as e:
        print(f"\n!!! FATAL ERROR during startup !!!")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)

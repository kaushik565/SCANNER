"""
Simple Windows test for Batch Setup dialog
Tests the batch configuration UI without hardware dependencies
"""

import sys
import os
import json
import csv
from datetime import datetime
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *

# Setup paths
SCANNER_PATH = os.path.dirname(os.path.abspath(__file__))
LOCATION_JSON = os.path.join(SCANNER_PATH, "location.json")
BATCH_LOGS = os.path.join(SCANNER_PATH, "Batch_Setup_Logs")

# Globals
batch_number = ""
line = "A"
cube = "1"
_mould_ranges = {}

# Import validation logic
try:
    from logic import handle_qr_scan
except:
    def handle_qr_scan(qr_code, batch_line, mould_ranges, duplicate_checker=None):
        return "OUT OF BATCH", None

def loadsettings():
    global line, cube, batch_number
    try:
        with open(LOCATION_JSON, "r") as f:
            data = json.load(f)
            cube = data.get('cube', '1')
            line = data.get('line', 'A')
            batch_number = data.get('batch_number', '').strip().upper()
    except Exception as e:
        print(f"Error loading settings: {e}")
        line = "A"
        cube = "1"
        batch_number = ""

def _load_mould_ranges(batch_no, line_letter):
    ranges = {}
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
                            if line_letter and ln and ln != line_letter:
                                continue
                            if mould and start and end:
                                ranges[mould] = (start, end)
                        except:
                            continue
                if ranges:
                    return ranges
        except:
            pass
    return ranges

class BatchSetupDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Setup")
        self.setModal(True)
        self.resize(700, 450)

        vbox = QtWidgets.QVBoxLayout(self)
        
        # Title
        title = QtWidgets.QLabel("Configure Batch and Mould Ranges")
        title_font = QtGui.QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        vbox.addWidget(title)
        
        form = QtWidgets.QFormLayout()

        self.batch_edit = QtWidgets.QLineEdit(self)
        self.batch_edit.setPlaceholderText("e.g., MVXYZ12345")
        
        self.line_edit = QtWidgets.QLineEdit(self)
        self.line_edit.setPlaceholderText("e.g., A")
        self.line_edit.setMaxLength(1)
        
        self.mould_count = QtWidgets.QSpinBox(self)
        self.mould_count.setRange(1, 64)
        self.mould_count.valueChanged.connect(self._rows_changed)

        try:
            self.batch_edit.setText(batch_number)
            self.line_edit.setText(line)
        except:
            pass

        form.addRow("Batch Number:", self.batch_edit)
        form.addRow("Line:", self.line_edit)
        form.addRow("Number of moulds:", self.mould_count)

        vbox.addLayout(form)
        
        # Instructions
        instr = QtWidgets.QLabel("Fill in the table below with mould type and QR range for each mould:")
        vbox.addWidget(instr)

        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Mould Type (3 chars)", "QR Start (14 chars)", "QR End (14 chars)"])
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
            
            if not bn:
                QtWidgets.QMessageBox.warning(self, "Missing data", "Please enter Batch Number")
                return
            if not ln or len(ln) != 1:
                QtWidgets.QMessageBox.warning(self, "Invalid Line", "Please enter a single letter for Line (e.g., A)")
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
                QtWidgets.QMessageBox.warning(self, "No moulds", "Please enter at least one mould with start/end QR codes")
                return

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
                print(f"Warning: Could not update location.json: {e}")

            global batch_number, line, _mould_ranges
            batch_number = bn
            line = ln
            _mould_ranges = _load_mould_ranges(batch_number, line)

            QtWidgets.QMessageBox.information(self, "Success", 
                f"Batch setup saved successfully!\n\n"
                f"File: {csv_path}\n"
                f"Batch: {bn}\n"
                f"Line: {ln}\n"
                f"Moulds: {len(entries)}")
            self.accept()
        except Exception as e:
            print(e)
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save: {e}")

class MainTestWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Batch Setup Tester")
        self.resize(900, 600)
        
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        
        # Header
        header = QtWidgets.QLabel("SCANNER - Batch Setup Test Tool")
        header_font = QtGui.QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(header)
        
        # Load settings
        loadsettings()
        global _mould_ranges
        _mould_ranges = _load_mould_ranges(batch_number, line)
        
        # Status info
        self.info_text = QtWidgets.QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        self.update_info()
        layout.addWidget(self.info_text)
        
        # QR Test section
        test_group = QtWidgets.QGroupBox("Test QR Validation")
        test_layout = QtWidgets.QVBoxLayout()
        
        qr_input_layout = QtWidgets.QHBoxLayout()
        qr_input_layout.addWidget(QtWidgets.QLabel("Enter QR Code:"))
        self.qr_input = QtWidgets.QLineEdit()
        self.qr_input.setPlaceholderText("Type QR code and press Enter (e.g., MAAA0000000500)")
        self.qr_input.returnPressed.connect(self.test_qr)
        qr_input_layout.addWidget(self.qr_input)
        test_button = QtWidgets.QPushButton("Test")
        test_button.clicked.connect(self.test_qr)
        qr_input_layout.addWidget(test_button)
        test_layout.addLayout(qr_input_layout)
        
        self.result_text = QtWidgets.QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(200)
        test_layout.addWidget(self.result_text)
        
        test_group.setLayout(test_layout)
        layout.addWidget(test_group)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        batch_setup_btn = QtWidgets.QPushButton("Open Batch Setup...")
        batch_setup_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 10px; font-size: 14px; }")
        batch_setup_btn.clicked.connect(self.open_batch_setup)
        
        reload_btn = QtWidgets.QPushButton("Reload Settings")
        reload_btn.clicked.connect(self.reload_settings)
        
        clear_btn = QtWidgets.QPushButton("Clear Results")
        clear_btn.clicked.connect(lambda: self.result_text.clear())
        
        quit_btn = QtWidgets.QPushButton("Quit")
        quit_btn.clicked.connect(self.close)
        
        btn_layout.addWidget(batch_setup_btn)
        btn_layout.addWidget(reload_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(quit_btn)
        layout.addLayout(btn_layout)
        
    def update_info(self):
        mould_info = ""
        if _mould_ranges:
            mould_info = f"<b>Loaded Moulds ({len(_mould_ranges)}):</b><br>"
            for mould, (start, end) in _mould_ranges.items():
                mould_info += f"&nbsp;&nbsp;• {mould}: {start} → {end}<br>"
        else:
            mould_info = "<b style='color:orange;'>No mould ranges configured. Click 'Open Batch Setup...' to configure.</b>"
        
        self.info_text.setHtml(f"""
        <h3>Current Configuration</h3>
        <b>Batch Number:</b> {batch_number or '(not set)'}<br>
        <b>Line:</b> {line}<br>
        <b>Cube:</b> {cube}<br>
        <b>Config File:</b> {LOCATION_JSON}<br>
        <hr>
        {mould_info}
        """)
    
    def open_batch_setup(self):
        dlg = BatchSetupDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.reload_settings()
    
    def reload_settings(self):
        loadsettings()
        global _mould_ranges
        _mould_ranges = _load_mould_ranges(batch_number, line)
        self.update_info()
        QtWidgets.QMessageBox.information(self, "Reloaded", 
            f"Settings reloaded!\n\nBatch: {batch_number}\nLine: {line}\nMoulds: {len(_mould_ranges)}")
    
    def test_qr(self):
        qr = self.qr_input.text().strip().upper()
        if not qr:
            return
        
        if not _mould_ranges:
            self.result_text.append(f"<div style='background-color:orange;color:white;padding:8px;margin:5px;'><b>WARNING:</b> No mould ranges configured. Please set up batch first.</div>")
            return
        
        try:
            status, mould = handle_qr_scan(qr, line, _mould_ranges, duplicate_checker=None)
            
            if status == "PASS":
                color = "#4CAF50"
                icon = "✓"
            elif status == "DUPLICATE":
                color = "#FF9800"
                icon = "⚠"
            else:
                color = "#F44336"
                icon = "✗"
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            result_html = f"""
            <div style='background-color:{color};color:white;padding:10px;margin:5px;border-radius:5px;'>
            <b>{icon} [{timestamp}]</b><br>
            <b>QR Code:</b> {qr}<br>
            <b>Status:</b> {status}<br>
            <b>Mould:</b> {mould or 'N/A'}<br>
            <b>Line:</b> {line}
            </div>
            """
            self.result_text.append(result_html)
            self.qr_input.clear()
            self.qr_input.setFocus()
            
        except Exception as e:
            self.result_text.append(f"<div style='background-color:#F44336;color:white;padding:10px;margin:5px;'><b>ERROR:</b> {e}</div>")

if __name__ == "__main__":
    print("=== Batch Setup Tester Starting ===")
    print(f"Working directory: {SCANNER_PATH}")
    
    # Ensure location.json exists
    if not os.path.exists(LOCATION_JSON):
        print("Creating default location.json...")
        with open(LOCATION_JSON, 'w') as f:
            json.dump({"line": "A", "cube": "1", "trigger": "0", "scanner": "1", "batch_number": ""}, f, indent=2)
    
    os.makedirs(BATCH_LOGS, exist_ok=True)
    
    try:
        app = QtWidgets.QApplication(sys.argv)
        app.setStyle('Fusion')
        
        window = MainTestWindow()
        window.show()
        
        print("Application started successfully!")
        print("Use 'Open Batch Setup...' to configure batch and moulds")
        
        sys.exit(app.exec_())
    except Exception as e:
        print(f"\n!!! ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)

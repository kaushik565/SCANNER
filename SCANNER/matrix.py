from datetime import datetime
import os, errno
import time
import io, re
import sqlite3
#import pandas as pd
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
# New validation modules
try:
    from duplicate_tracker import DuplicateTracker
    from logic import handle_qr_scan
except Exception as _e:
    # Fallback no-op shims if modules are unavailable during import-time
    DuplicateTracker = None  # type: ignore
    def handle_qr_scan(qr_code, batch_line, mould_ranges, duplicate_checker=None):  # type: ignore
        return "OUT OF BATCH", None
import settings
import getpass
import socket
import fcntl
import struct
import signal
import serial
import threading
import select
import binascii
import mmap
mutex_wrkrbusy = threading.Lock()

# Get the directory where matrix.py is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

cube="NA"
line="NA"
batch_number = ""  # Added: batch number for new validation
_mould_ranges = {}   # Added: mould ranges loaded from setup file
user="NA"
trigger=False
inscanner=True
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
        return "No network"

def loadsettings():
    global cube,line,user,trigger,inscanner,batch_number
    location_file = os.path.join(SCRIPT_DIR, 'location.json')
    with open(location_file, "r") as jason_in:
        data = json.load(jason_in) 
        global line,cube,trigger,inscanner,batch_number
        cube=data['cube']
        line=data['line']
        if data['trigger']=='1':
            trigger=True
        else:
            trigger=False
        if data['scanner']=='1':
            inscanner=True
        else:
            inscanner=False 
        # Optional batch number for validation
        batch_number = data.get('batch_number', '').strip().upper() if isinstance(data, dict) else ""

def _load_mould_ranges(batch_no: str, line_letter: str):
    """Load mould ranges from CSV/JSON files into a dict: {mould: (start,end)}.
    Tries files in this order:
      SCRIPT_DIR/Batch_Setup_Logs/{batch}_setup.csv (preferred)
      SCRIPT_DIR/{batch}_setup.csv
      SCRIPT_DIR/batch_setup.csv
      SCRIPT_DIR/batch_setup.json
    """
    ranges = {}
    import os, csv
    candidates = []
    if batch_no:
        candidates.append(os.path.join(SCRIPT_DIR, 'Batch_Setup_Logs', f'{batch_no}_setup.csv'))
        candidates.append(os.path.join(SCRIPT_DIR, f'{batch_no}_setup.csv'))
    candidates.append(os.path.join(SCRIPT_DIR, 'batch_setup.csv'))
    # Try CSV first
    for path in candidates:
        try:
            if os.path.exists(path):
                with open(path, 'r', newline='') as fh:
                    reader = csv.reader(fh)
                    header = next(reader, None)
                    # Expect header: BatchNo, Line, MouldType, QR_Start, QR_End
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
    # Try JSON fallback
    try:
        jpath = os.path.join(SCRIPT_DIR, 'batch_setup.json')
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
                    
# Batch Setup dialog placed before Window2 to satisfy static analyzers
    

class Window2(QMainWindow):   
    global line,cube,user,trigger
    def __init__(self):
        super(Window2, self).__init__()
        self.w = settings.Ui_SETTINGSw()
        self.w.setupUi(self)
        
        self.cubet=cube
        self.linet=line
        self.triggert=trigger
        self.inscannert=inscanner
        
        font = QtGui.QFont()
        font.setPointSize(36)
        font.setCapitalization(QFont.AllUppercase)
        self.w.spinBoxline.setFont(font)
        
        #font = w.spinBoxcube.font()
        #font.setCapitalization(QFont.AllUppercase)
        self.w.spinBoxcube.setFont(font)
        
        self.w.curline.setText("Current line: "+line)
        self.w.curcube.setText("Current cubicle: "+cube)
        
        self.w.spinBoxline.setProperty("value", int(line, 32))
        self.w.spinBoxcube.setProperty("value", cube)
        
        self.w.checkBox.setChecked(self.triggert)
        self.w.checkBox_2.setChecked(self.inscannert)


        self.w.save.clicked.connect(self.save_clicked)
        self.w.exit.clicked.connect(self.exit_clicked)
        self.w.pushButton.clicked.connect(self.bluetooth_clicked)
        #resetcount
        self.w.pushButton_2.clicked.connect(self.reset_clicked)
        
        
        self.w.label_2 = QLabel('Version:1.0', self)
        pal = self.w.label_2.palette()
        pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor("red"))
        self.w.label_2.setPalette(pal)
        self.w.label_2.move(330, 1)
        #self.w.label_2.setGeometry(QtCore.QRect(330, 5, 141, 20))
        #self.w.label_2.setStyleSheet("background-color: rgba(255, 255, 255, 90);") 
        self.w.label_2.setHidden(False)

        # Added: Batch number input (stored in /SCANNER/location.json)
        try:
            self.w.label_batch = QLabel('Batch Number', self.w.centralwidget)
            self.w.label_batch.setGeometry(QtCore.QRect(280, 200, 161, 31))
            font2 = QtGui.QFont()
            font2.setPointSize(12)
            self.w.label_batch.setFont(font2)

            self.w.batch_edit = QtWidgets.QLineEdit(self.w.centralwidget)
            self.w.batch_edit.setGeometry(QtCore.QRect(280, 235, 191, 36))
            bf = QtGui.QFont(); bf.setPointSize(14)
            self.w.batch_edit.setFont(bf)
            self.w.batch_edit.setText(batch_number if isinstance(batch_number, str) else "")

            # New: Batch Setup button to open mould range editor
            self.w.batch_setup_btn = QtWidgets.QPushButton(self.w.centralwidget)
            self.w.batch_setup_btn.setGeometry(QtCore.QRect(280, 280, 191, 36))
            self.w.batch_setup_btn.setText('Batch Setup...')
            self.w.batch_setup_btn.clicked.connect(self.open_batch_setup)
        except Exception as _e:
            pass

    def open_batch_setup(self):
        try:
            dlg = BatchSetupDialog(self)
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                # Refresh labels in settings window after save
                loadsettings()
                # Refresh global mould ranges in memory
                global _mould_ranges
                _mould_ranges = _load_mould_ranges(batch_number, line)
                self.w.curline.setText("Current line: "+line)
                self.w.curcube.setText("Current cubicle: "+cube)
        except Exception as e:
            print(e)

    @QtCore.pyqtSlot()   
    def save_clicked(self):
        global trigger
        convTable = ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V')
        self.linet=str(convTable[self.w.spinBoxline.value()])
        self.cubet=str(self.w.spinBoxcube.value())
        location_file = os.path.join(SCRIPT_DIR, 'location.json')
        with open(location_file, "r+") as outfile: 
            data = json.load(outfile)
            data["line"] =self.linet
            data["cube"] =self.cubet
            if self.w.checkBox.isChecked() == True:
                data["trigger"]='1'
            else:
                data["trigger"]='0'
            if self.w.checkBox_2.isChecked() == True:
                data["scanner"]='1'
            else:
                data["scanner"]='0'
            # Save batch number if present
            try:
                bval = self.w.batch_edit.text().strip().upper()
                data["batch_number"] = bval
            except Exception:
                pass
            outfile.seek(0)  # rewind
            json.dump(data, outfile)
            outfile.truncate()

        loadsettings()
        
        self.w.curline.setText("Current line : "+line)
        self.w.curcube.setText("Current cubicle : "+cube)
        self.w.checkBox.setChecked(trigger)
        self.w.checkBox_2.setChecked(inscanner)
        
        # Close settings window and show main window
        try:
            if hasattr(self, 'main_window') and self.main_window:
                # Reload mould ranges with new batch data
                global _mould_ranges
                _mould_ranges = _load_mould_ranges(batch_number, line)
                print(f"Reloaded mould ranges: {len(_mould_ranges)} moulds for batch {batch_number}")
                
                # Update batch display in MATRIX field
                if batch_number:
                    self.main_window.ui.MATRIX_EDIT.setText(f'BATCH: {batch_number}')
                else:
                    self.main_window.ui.MATRIX_EDIT.setText('BATCH: NOT SET')
                
                # Update workstation display with new batch info
                self.main_window.updatejigip()
                
                self.main_window.show()
                # Don't restart threads - they should still be running
            self.close()
        except Exception as e:
            print(e)
        
        
    @QtCore.pyqtSlot()    
    def reset_clicked(self): 
        
        self.matrix_db = sqlite3.connect(os.path.join(SCRIPT_DIR, 'scanner.db'))    
        
        with open(os.path.join(SCRIPT_DIR, 'cat'), "w") as fc:
            cursor6 = self.matrix_db.cursor()#
            cursor6.execute('''SELECT SEQ from sqlite_sequence WHERE name='cartridge';''')
            fc.write(str(cursor6.fetchone()[0])) 
            cursor6.close()    
    
        #print("reset")
    
    @QtCore.pyqtSlot()  
    def exit_clicked(self):
        print("exit") 
        sys.exit()
        
    @QtCore.pyqtSlot()  
    def bluetooth_clicked(self):
        with open("/tmp/python_c_sync/dmy", "w") as f:
            f.seek(0)
            f.write("nothing")


class BatchSetupDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Setup")
        self.setModal(True)
        self.resize(600, 420)

        # Layouts
        vbox = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        vbox.addLayout(form)

        # Inputs
        self.batch_edit = QtWidgets.QLineEdit(self)
        self.line_edit = QtWidgets.QLineEdit(self)
        self.mould_count = QtWidgets.QSpinBox(self)
        self.mould_count.setRange(1, 64)
        self.mould_count.valueChanged.connect(self._rows_changed)

        # Prefill from globals
        try:
            self.batch_edit.setText(batch_number)
            self.line_edit.setText(line)
        except Exception:
            pass

        form.addRow("Batch Number", self.batch_edit)
        form.addRow("Line", self.line_edit)
        form.addRow("Number of moulds", self.mould_count)

        # Table for mould ranges
        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["MouldType", "QR_Start", "QR_End"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        vbox.addWidget(self.table)

        # Buttons
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel, self)
        btns.accepted.connect(self._save_and_close)
        btns.rejected.connect(self.reject)
        vbox.addWidget(btns)

        # Initialize rows from existing ranges
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
        # Ensure cells exist
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

            # Write CSV
            import os, csv
            folder = os.path.join(SCRIPT_DIR, 'Batch_Setup_Logs')
            try:
                os.makedirs(folder, exist_ok=True)
            except Exception:
                pass
            csv_path = os.path.join(folder, f'{bn}_setup.csv')
            with open(csv_path, "w", newline="") as fh:
                wr = csv.writer(fh)
                wr.writerow(["BatchNo", "Line", "MouldType", "QR_Start", "QR_End"])
                for mould, start, end in entries:
                    wr.writerow([bn, ln, mould, start, end])

            # Update location.json with batch_number and line
            try:
                location_file = os.path.join(SCRIPT_DIR, 'location.json')
                with open(location_file, 'r+') as jf:
                    data = json.load(jf)
                    data['batch_number'] = bn
                    data['line'] = ln
                    jf.seek(0)
                    json.dump(data, jf)
                    jf.truncate()
            except Exception as e:
                print(e)

            # Update globals for immediate use
            global batch_number, line, _mould_ranges
            batch_number = bn
            line = ln
            _mould_ranges = _load_mould_ranges(batch_number, line)

            self.accept()
        except Exception as e:
            print(e)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save: {e}")


def close_gpio(fd,pin):
        try:
            os.close(fd)
        except OSError as e:
            raise OSError(e.errno, "Closing GPIO: " + e.strerror)
        gpio_path = "/sys/class/gpio/gpio%d" % pin
        if not os.path.isdir(gpio_path):
            try:
                with open("/sys/class/gpio/unexport", "w") as f_export:
                    f_export.write("%d\n" % pin)
            except IOError as e:
                print("Export:"+str(e))     
     
def set_gpio(fd,value):
    try:
        if value:
            os.write(fd, b"1\n")
        else:
            os.write(fd, b"0\n")
    except OSError as e:
        raise OSError(e.errno, "Writing GPIO: " + e.strerror)
    try:
        os.lseek(fd, 0, os.SEEK_SET)
    except OSError as e:
        raise OSError(e.errno, "Rewinding GPIO: " + e.strerror)

def safe_set_gpio(fd, value, label="GPIO"):
    """Set GPIO value only if file descriptor is valid; log otherwise."""
    if fd is None:
        print(f"{label}: skipped set (fd=None)")
        return
    try:
        set_gpio(fd, value)
    except Exception as e:
        print(f"{label}: set failed: {e}")
          
def poll_gpio(fd):
    p = select.epoll()
    p.register(fd, select.EPOLLIN | select.EPOLLET | select.EPOLLPRI)
    # Poll twice, as first call returns with current state
    for _ in range(2):
        events = p.poll(None)
    # If GPIO edge interrupt occurred
    if events:
        # Rewind
        try:
            os.lseek(fd, 0, os.SEEK_SET)
        except OSError as e:
            raise OSError(e.errno, "Rewinding GPIO: " + e.strerror)    
        
def init_gpio(pin, direction, edge="rising"):
    # Supported directions: "in", "out", "high", "low"
    # "high"/"low" are not accepted on some kernels for the 'direction' file.
    # In that case, fall back to: set direction "out" then write value 1/0.
    gpio_path = "/sys/class/gpio/gpio%d" % pin
    try:
        if not os.path.isdir(gpio_path):
            # Export the pin
            try:
                with open("/sys/class/gpio/export", "w") as f_export:
                    f_export.write("%d\n" % pin)
            except Exception as e:
                # Permission or unsupported sysfs
                print(f"GPIO export failed for {pin}: {e}")
                return None
            # Wait briefly for sysfs to create the directory
            for _ in range(20):  # ~400ms max
                if os.path.isdir(gpio_path):
                    break
                time.sleep(0.02)

        # Set direction
        want_level = None
        if direction in ("high", "low"):
            want_level = 1 if direction == "high" else 0
            write_dir = direction
        else:
            write_dir = direction

        try:
            with open(f"{gpio_path}/direction", "w") as f_direction:
                f_direction.write(write_dir + "\n")
        except IOError as e:
            # Some kernels don't accept "high"/"low". Fall back to "out".
            if write_dir in ("high", "low"):
                try:
                    with open(f"{gpio_path}/direction", "w") as f_direction:
                        f_direction.write("out\n")
                except IOError as e2:
                    print(f"GPIO set direction failed for {pin}: {e2}")
                    return None
            else:
                print(f"GPIO set direction failed for {pin}: {e}")
                return None

        # Open value file
        try:
            fd = os.open(f"{gpio_path}/value", os.O_RDWR)
        except OSError as e:
            print(f"GPIO open value failed for {pin}: {e}")
            return None

        # If requested 'high'/'low' and kernel didn't take it in 'direction', set value explicitly
        if want_level is not None:
            try:
                set_gpio(fd, want_level)
            except Exception as e:
                print(f"GPIO set initial level failed for {pin}: {e}")

        # Configure edge for inputs
        if direction == 'in':
            try:
                with open(f"{gpio_path}/edge", "w") as f_edge:
                    f_edge.write(edge + "\n")
            except IOError as e:
                print(f"GPIO set edge failed for {pin}: {e}")
        return fd
    except Exception as e:
        print(f"GPIO init unexpected error for {pin}: {e}")
        return None           

class matrix_gui(QtWidgets.QDockWidget):
    def __init__(self):
        global line, cube, user, trigger, inscanner, batch_number, _mould_ranges
        try:
            print("matrix_gui.__init__ starting...")
            super(matrix_gui, self).__init__()
            self.ui = matrixux.Ui_DockWidget()
            #self.ui.setWindowFlag(Qt.FramelessWindowHint) 
            self.ui.setupUi(self)
            self.setGeometry(0, 0, 480, 325) 
            print("UI setup complete")

            # QR Input field - back to original position but styled
            self.ui.qr_input = QtWidgets.QLineEdit(self.ui.dockWidgetContents)
            self.ui.qr_input.setGeometry(QtCore.QRect(440, 10, 300, 35))
            self.ui.qr_input.setReadOnly(False)
            self.ui.qr_input.setPlaceholderText("Scan QR...")
            self.ui.qr_input.setFocus()
            self.ui.qr_input.returnPressed.connect(self.qrinput)
            self.ui.qr_input.setFocusPolicy(Qt.StrongFocus)
            qr_inputfont= QtGui.QFont()
            qr_inputfont.setPointSize(14)
            qr_inputfont.setBold(False)
            self.ui.qr_input.setFont(qr_inputfont)
            self.ui.qr_input.setStyleSheet("""
                QLineEdit {
                    background-color: white;
                    color: black;
                    border: 2px solid #2196F3;
                    padding: 3px;
                }
            """)
            
            
            print("Loading settings...")
            loadsettings()
            print(f"Settings loaded: line={line}, cube={cube}, trigger={trigger}, inscanner={inscanner}, batch_number={batch_number}")

            try :
                print("Opening UART /dev/ttyS0...")
                self.uart = serial.Serial('/dev/ttyS0', baudrate=115200, timeout=None,
                            parity=serial.PARITY_NONE,
                            stopbits=serial.STOPBITS_ONE,
                            bytesize=serial.EIGHTBITS
                            )
                print("UART opened successfully")
                
                # Initialize GPIO 18 to signal PIC that Pi is ready
                # This clears the "INITIALIZING" message and "SBC ER-1" error
                if self._set_ready_signal():
                    print("Ready signal asserted (GPIO 18 HIGH)")
                else:
                    print("WARNING: Failed to assert ready signal on GPIO 18")
                
            except Exception as e:
                print("UART. init:"+datetime.now().strftime("%Y/%m/%d-%H:%M:%S"))
                print(e)
                # Comment out error dialog to see if this is blocking startup
                # self.signals.error_signal.emit('UART not found! - '+str(e),'UART init. error')
                print("WARNING: UART not available, continuing anyway for testing...")
                self.uart = None  # Allow app to start without UART for testing
                
            self.mutex = QMutex()
            self.cond = QWaitCondition()    

            self.threadpool = QThreadPool()
            print("Creating worker threads...")
            
            self.worker = Worker(self.mutex,self.cond,self.uart)
            self.timerthread =TimerThread(self.ui)
            if inscanner==True:
                self.serialcom=SerialThread(self.cond, self.uart)
            #self.shutdownmonitor=ShutdownThread()
            

            
            self.ui.MATRIX_EDIT.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)    
            self.ui.CARTRIDGE_EDIT.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            print("Connecting signals...")
            self.worker.signals.change_value_matrix.connect(self.set_MATRIX_EDIT)
            self.worker.signals.change_value_cartridge.connect(self.set_CARTRIDGE_EDIT)
            #self.worker.signals.change_value_count.connect(self.set_CARTRIDGE_COUNT)
            
            self.worker.signals.change_acceptvalue_count.connect(self.set_CARTRIDGE_COUNT_1)
            self.worker.signals.change_rejectvalue_count.connect(self.set_CARTRIDGE_COUNT_2)
            
            
            self.worker.signals.change_value_errors.connect(self.set_ERRORS)
            self.worker.signals.error_signal.connect(self.showdialog)
            self.ui.pushButton_4.setEnabled(False)
            
            if inscanner==True:
                self.serialcom.signals.error_signal.connect(self.showdialog)  
                
            #self.shutdownmonitor.signals.ShutdownSignal.connect(self.shutdown_poc)
            if trigger==True:   
                self.ui.label_2 = QLabel(' WAITING FOR TRIGGER...', self)
                #self.ui.label_2.move(140, 100)
                #self.ui.label_2.setGeometry(QtCore.QRect(23, 210, 225, 25))
                self.ui.label_2.setGeometry(QtCore.QRect(33, 310, 225, 25))
                self.ui.label_2.setStyleSheet("background-color: rgba(255, 255, 255, 90);") 
                self.ui.label_2.setHidden(True)
                if inscanner==True:
                    self.serialcom.signals.waitfortrigon.connect(self.trigwaiton)
                    self.serialcom.signals.waitfortrigoff.connect(self.trigwaitoff)
                    self.ui.pushButton_4.setEnabled(True)
                    self.ui.pushButton_4.clicked.connect(self.trig_scan)
                    
            
                
            self.ui.pushButton_2.clicked.connect(self.logoff)

            self.timerthread.signals.update_time.connect(self.updatetime)
            self.timerthread.signals.update_jigdetails.connect(self.updatejigdetails)
            self.timerthread.signals.update_jigip.connect(self.updatejigip)
            self.timerthread.signals.error_signal.connect(self.showdialog)

            user=getpass.getuser()
            if user=="Operator":
                self.ui.pushButton.setEnabled(False)
                self.ui.pushButton_3.setEnabled(False)
            else :
                self.ui.pushButton.clicked.connect(self.window2)
                self.ui.pushButton_3.clicked.connect(self.show_keyboard)
                
            self.ui.WRKSTNin.setFontPointSize(18);
            self.ui.WRKSTNin.setTextColor(QColor(0, 0, 255));
            self.ui.WRKSTNin.setFontWeight(QtGui.QFont.Normal)

            self.ui.MATRIX_EDIT.setFontPointSize(18);#fs
            self.ui.MATRIX_EDIT.setTextColor(QColor(255, 0, 0));
            self.ui.MATRIX_EDIT.setFontWeight(QtGui.QFont.Bold)
            
            self.ui.CARTRIDGE_EDIT.setFontPointSize(18);#18
            self.ui.CARTRIDGE_EDIT.setTextColor(QColor(255, 0, 0));
            self.ui.CARTRIDGE_EDIT.setFontWeight(QtGui.QFont.Bold)
            
            self.ui.CARTRIDGE_EDIT.setText('SCAN CARTRIDGE')
            
            # Show batch number in MATRIX field instead of yellow label
            if batch_number:
                self.ui.MATRIX_EDIT.setText(f'BATCH: {batch_number}')
            else:
                self.ui.MATRIX_EDIT.setText('BATCH: NOT SET')
            
            # Display workstation info with batch number
            batch_info = f"  Batch: {batch_number}" if batch_number else "  Batch: Not Set"
            print(f"Initial workstation display - batch_number: '{batch_number}'")
            self.ui.WRKSTNin.setText("Line : "+line+"\t                                                               "+"Cubicle : "+cube+"\t                                        "+"User : "+user+batch_info+'\n'+'Jig ID : '+self.ui.host+"\t                                                                                                    "+"IP : Fetching")
            
            
            

            # Load mould ranges for validation
            global _mould_ranges
            _mould_ranges = _load_mould_ranges(batch_number, line)
            print(f"Mould ranges loaded: {len(_mould_ranges)} moulds")

            print("Starting worker threads...")
            self.threadpool.start(self.worker)
            self.threadpool.start(self.timerthread)
            if inscanner==True:
                self.threadpool.start(self.serialcom)
            #self.threadpool.start(self.shutdownmonitor)
            
            print("matrix_gui initialization complete!")
            
            
            
            
            
        except Exception as e:
                print(f"!!! Exception in matrix_gui.__init__: {e}")
                import traceback
                traceback.print_exc()
                raise

    def _set_ready_signal(self):
        """
        Assert the PIC ready signal by driving GPIO 18 HIGH.
        Returns True on success, False otherwise.
        Tries sysfs first; if that fails, attempts raspi-gpio fallback.
        """
        pin = 18
        fd = init_gpio(pin, 'high')
        if fd is not None:
            try:
                set_gpio(fd, 1)
                self.sbc_ready_pin = fd
                return True
            except Exception as e:
                print(f"Ready signal set_gpio failed: {e}")
        # Fallback using raspi-gpio (requires binary and usually root privileges)
        try:
            rc = subprocess.call(["raspi-gpio", "set", str(pin), "op", "dh"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if rc == 0:
                print("raspi-gpio fallback used for ready signal")
                self.sbc_ready_pin = None
                return True
            else:
                print(f"raspi-gpio fallback failed rc={rc}")
        except FileNotFoundError:
            print("raspi-gpio not installed; can't use fallback")
        except Exception as e:
            print(f"raspi-gpio fallback exception: {e}")
        # Fallback using RPi.GPIO (access via /dev/gpiomem)
        try:
            import RPi.GPIO as RGPIO
            RGPIO.setwarnings(False)
            RGPIO.setmode(RGPIO.BCM)
            # Try cleanup first in case pin was left in use
            try:
                RGPIO.cleanup(pin)
            except:
                pass
            RGPIO.setup(pin, RGPIO.OUT, initial=RGPIO.HIGH)
            # Force output HIGH and verify
            RGPIO.output(pin, RGPIO.HIGH)
            time.sleep(0.1)
            # Read back to verify (if possible)
            try:
                state = RGPIO.input(pin)
                print(f"RPi.GPIO fallback used for ready signal (BCM{pin} readback={state})")
            except:
                print(f"RPi.GPIO fallback used for ready signal (BCM{pin})")
            self._ready_backend = ("RPi.GPIO", pin)
            self._gpio_obj = RGPIO
            return True
        except ImportError:
            print("RPi.GPIO not installed; skipping fallback")
        except Exception as e:
            print(f"RPi.GPIO fallback exception: {e}")
        # Fallback using libgpiod (python3-libgpiod)
        try:
            import gpiod
            chip = gpiod.Chip('gpiochip0')
            line = chip.get_line(pin)
            # Release if already requested (cleanup from previous run)
            try:
                line.release()
            except:
                pass
            line.request(consumer='scanner', type=gpiod.LINE_REQ_DIR_OUT, default_val=1)
            print("libgpiod fallback used for ready signal")
            self._gpiod_chip = chip
            self._gpiod_line = line
            return True
        except ImportError:
            print("libgpiod (python3-libgpiod) not installed; skipping fallback")
        except Exception as e:
            print(f"libgpiod fallback exception: {e}")
        return False
    """ 
    def shutdown_poc(self):
        try:
            self.serialcom.stop()
            self.worker.stop()
            #self.hide()
            subprocess.Popen('systemctl poweroff -i',shell=True)
            sys.exit()
        except Exception as e:
            print(e)
    """
    @QtCore.pyqtSlot()
    def trigwaitoff(self):
        self.ui.label_2.setHidden(True) 
    @QtCore.pyqtSlot()
    def trigwaiton(self):
        self.ui.label_2.setHidden(False) 
        
    @QtCore.pyqtSlot(str,str)              
    def showdialog(self,text,error_type):
        try:
            global user
            if inscanner==True:
                self.serialcom.stop()
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText(error_type)
            if error_type=='In-built QR Reader error' and user=="Operator":
                msg.setInformativeText(text+"\nGo to Settings for disabling in-built QR Reader")
            else:
                msg.setInformativeText(text)
            msg.setWindowTitle("ERROR")
            msg.setStandardButtons(QMessageBox.Ok)
            #self.hide()
            msg.exec_()
            # Don't stop threads or exit - just show warning and continue
            # User can still use keyboard input for QR codes
            # if inscanner==True:
            #     self.serialcom.stop()
            # self.worker.stop()
            # if error_type=='In-built QR Reader error':
            #     if user=="Operator":
            #         self.logoff()
            #     else:
            #         self.window2()
            # sys.exit()
            
        except Exception as e:
            print(e)        
    def window2(self):
        # Don't stop threads when opening settings
        # if inscanner==True:
        #     self.serialcom.stop()
        # self.worker.stop()
        self.w = Window2()
        self.w.main_window = self  # Store reference to main window
        self.w.show()
        self.hide()
    def trig_scan(self):
        #set_gpio(21,1)    
        global text     
        ser = serial.Serial('/dev/qrscanner', baudrate=115200, timeout=5,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        bytesize=serial.EIGHTBITS
                        )
        tgr_cmd= [0x7E, 0x00, 0x08, 0x01, 0x00, 0x02, 0x01, 0xAB, 0xCD,0x00]
        "".join(map(chr, tgr_cmd))
        ser.write(tgr_cmd)
        read_buf=ser.read(size=7)
        if (read_buf[0] == 0x02 and  read_buf[1] == 0x00 and read_buf[2] == 0x00 and  read_buf[3] == 0x01 and  read_buf[4] == 0x00 and  read_buf[5] == 0x33 and  read_buf[6] == 0x31)!=0:
            text_in=ser.readline(50)
            #text_in=bytes((x for x in text_in if x >= 0x20 and x < 127))
            text_in=text_in.decode() 
            #print('raw qr:'+str(text_in))
            text_in=text_in.strip()
            if len(text_in)>3:
                if text_in != text: 
                    #time.sleep(5)
                    text=text_in
                    self.cond.wakeAll()
                else :
                    time.sleep(0.1)
        
    def show_keyboard(self):
        subprocess.Popen('onboard -x 55 -y 210 -s 690x230',shell=True)
        self.ui.qr_input.setFocus()
        self.keybrdclose = QtWidgets.QPushButton(self.ui.dockWidgetContents)
        self.keybrdclose.setGeometry(QtCore.QRect(50, 128, 250, 36))
        self.keybrdclose.setText('Close Keyboard')
        self.keybrdclose.clicked.connect(self.hide_keyboard)
        self.keybrdclose.show()
        
    def hide_keyboard(self):
        subprocess.Popen('pkill onboard',shell=True)
        self.keybrdclose.clicked.disconnect(self.hide_keyboard)
        self.keybrdclose.setParent(None)
        self.keybrdclose.deleteLater()
    
    def logoff(self):
        if inscanner==True:
            self.serialcom.stop()
        self.worker.stop()
        cmd = 'pkill -u '+user
        os.system(cmd)
        
    @QtCore.pyqtSlot()  
    def qrinput(self):
        global text
        text_in = self.ui.qr_input.text()
        self.ui.qr_input.clear()
        self.ui.qr_input.setFocus()
        try:
            if text_in != text:          
                self.cond.wakeAll()
                text=text_in
        except Exception as e:
            print(e)
           
    @QtCore.pyqtSlot()  
    def updatetime(self):
        self.ui.TIMEin.setText(datetime.now().strftime("%I:%M %p"))

    @QtCore.pyqtSlot()
    def updatejigdetails(self):
        try:   
            self.ui.DATEin.setText(datetime.now().strftime("%d/%m/%y"))
        except Exception as e:
            print(e)

    @QtCore.pyqtSlot()
    def updatejigip(self):
    
        try:
            #self.ui.IPin.setText()
            ip=get_ip_address('wlan0')
            if len(ip) < 6:
                ip='No network'
            batch_info = f"  Batch: {batch_number}" if batch_number else ""
            self.ui.WRKSTNin.setText("Line : "+line+"\t             "+"Cubicle : "+cube+"\t             "+"User : "+user+batch_info+'\n'+'Jig ID : '+self.ui.host+"\t             "+"IP : "+ip)
        except Exception as e:
            print(e)            
            
    @QtCore.pyqtSlot(str)   
    def set_MATRIX_EDIT(self, text):
        #print(self.ui)
        try:
            #print(text+"mat edit\n")
            # Don't overwrite batch number with error messages
            if text and not text.startswith('SBC ER'):
                self.ui.MATRIX_EDIT.setText(text)
            #
        except Exception as e:
            print(e)
    
    @QtCore.pyqtSlot(str)     
    def set_CARTRIDGE_EDIT(self, text):
        try:
            #print(text+"mat edit\n")
            self.ui.CARTRIDGE_EDIT.setText(text)
        except Exception as e:
            print(e)
       
    @QtCore.pyqtSlot(str)    
    #def set_CARTRIDGE_COUNT(self, text):
       # try:
       #     #print(text+"mat edit\n")
        ##    self.ui.CARTRIDGE_COUNT.setText(text)
       # except Exception as e:
         #   print(e)
    
    def set_CARTRIDGE_COUNT_1(self, text):
        try:
            #print(text+"mat edit\n")
            self.ui.CARTRIDGE_COUNT_1.setText(text)
        except Exception as e:
            print(e)
    
    def set_CARTRIDGE_COUNT_2(self, text):
        try:
            #print(text+"mat edit\n")
            self.ui.CARTRIDGE_COUNT_2.setText(text)
        except Exception as e:
            print(e)       
            
    @QtCore.pyqtSlot(str)     
    def set_ERRORS(self, text):
        try:
            print(text+" error\n")
        except Exception as e:
            print(e)

class SerialSignals(QObject):
    error_signal=pyqtSignal(str,str)
    waitfortrigon=pyqtSignal()
    waitfortrigoff=pyqtSignal()

class SerialThread(QRunnable):
    def __init__(self, cond, ser_uart):
        super(SerialThread, self).__init__()
        self.signals = SerialSignals()
        self.cond=cond
        self.running=True
        self.trig=trigger
        self.uart=ser_uart
    def stop(self):
        self.running=False
        try:
            self.running=False
            if self.trig==True:
                safe_set_gpio(self.status_pin,0,'STATUS_PIN')
                close_gpio(self.trigger_pin,20)
                close_gpio(self.status_pin,21)
            if hasattr(self, 'ser') and self.ser:
                self.ser.close()
            if mutex_wrkrbusy.locked():
                mutex_wrkrbusy.release()
        except Exception as e:
                print(e)
    def run(self):
        global text, mutex_wrkrbusy,synch_serialthread
        self.ser = None  # Initialize as None
        try :
            self.ser = serial.Serial('/dev/qrscanner', baudrate=115200, timeout=5,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        bytesize=serial.EIGHTBITS
                        )
        except Exception as e:
            print("Ser. init:"+datetime.now().strftime("%Y/%m/%d-%H:%M:%S"))
            print(e)
            print("WARNING: QR scanner not available - running in keyboard input mode")
            self.signals.error_signal.emit('Inbuilt QR Reader not found! - '+str(e),'In-built QR Reader error')
            # Don't exit - allow keyboard input mode
            return
        
        qr_tgr_cmd= [0x7E, 0x00, 0x08, 0x01, 0x00, 0x02, 0x01, 0xAB, 0xCD,0x00]
        "".join(map(chr, qr_tgr_cmd))
        self.sbc_busy_pin = init_gpio(18,'high')
        safe_set_gpio(self.sbc_busy_pin,1,'BUSY_PIN')
        if self.trig==True:
            self.trigger_pin = init_gpio(20,'in','rising')
            if self.trigger_pin is None:
                self.signals.error_signal.emit('Trigger GPIO init failed','GPIO Init error')
            self.status_pin = init_gpio(21,'high')
            if self.status_pin is None:
                self.signals.error_signal.emit('Status GPIO init failed','GPIO Init error')
        while synch_serialthread == 1:
            time.sleep(0.1)
        while self.running:
            mutex_wrkrbusy.acquire(blocking=True) 
            try:   
                if self.trig==True:
                    self.signals.waitfortrigon.emit()
                    safe_set_gpio(self.status_pin,1,'STATUS_PIN')
                    safe_set_gpio(self.sbc_busy_pin,1,'BUSY_PIN')
                    #poll_gpio(self.trigger_pin)
                    uart_buf=[0,0]
                    while True:
                        uart_buf=self.uart.read(size=1)
                        print (uart_buf)
                        if uart_buf[0] == 20:
                            break
                    
                    self.signals.waitfortrigoff.emit()
                    safe_set_gpio(self.status_pin,0,'STATUS_PIN')
                    safe_set_gpio(self.sbc_busy_pin,0,'BUSY_PIN')
                self.ser.flush()
                #time.sleep(3)
                try:
                    print("Triggering")
                    self.ser.write(qr_tgr_cmd)
                    read_buf=self.ser.read(size=7)
                    print("CMD ERR: "+ str(read_buf[0])+'|'+ str(read_buf[1])+'|'+  str(read_buf[2])+'|'+  str(read_buf[3])+'|'+ str(read_buf[4])+'|'+  str(read_buf[5])+'|'+ str( read_buf[6]))
                except Exception as e:
                    print("Serial QR command exception:")
                    print(e)
                    tgr_cmd= [81]  #Q
                    "".join(map(chr, tgr_cmd))
                    self.uart.write(tgr_cmd)
                    try :
                        self.ser = serial.Serial('/dev/qrscanner', baudrate=115200, timeout=5,
                                    parity=serial.PARITY_NONE,
                                    stopbits=serial.STOPBITS_ONE,
                                    bytesize=serial.EIGHTBITS
                                    )
                    except Exception as e:
                        print("Ser. init:"+datetime.now().strftime("%Y/%m/%d-%H:%M:%S"))
                        print(e)
                        self.signals.error_signal.emit('Inbuilt QR Reader not found! - '+str(e),'In-built QR Reader error')
                        time.sleep(255)
                        sys.exit()
                    continue
                try: 
                    if (read_buf[0] == 0x02 and  read_buf[1] == 0x00 and read_buf[2] == 0x00 and  read_buf[3] == 0x01 and  read_buf[4] == 0x00 and  read_buf[5] == 0x33 and  read_buf[6] == 0x31)!=0:
                        try:
                            text_in=self.ser.readline(50)
                        except Exception as e:
                            print("Serial QR read exception:")
                            print(e)
                            tgr_cmd= [81]  #Q
                            "".join(map(chr, tgr_cmd))
                            self.uart.write(tgr_cmd)
                            try :
                                self.ser = serial.Serial('/dev/qrscanner', baudrate=115200, timeout=5,
                                            parity=serial.PARITY_NONE,
                                            stopbits=serial.STOPBITS_ONE,
                                            bytesize=serial.EIGHTBITS
                                            )
                            except Exception as e:
                                print("Ser. init:"+datetime.now().strftime("%Y/%m/%d-%H:%M:%S"))
                                print(e)
                                self.signals.error_signal.emit('Inbuilt QR Reader not found! - '+str(e),'In-built QR Reader error')
                                time.sleep(255)
                                sys.exit()
                            continue
                        #text_in=bytes((x for x in text_in if x >= 0x20 and x < 127))
                        text_in=text_in.decode() 
                        #print('raw qr:'+str(text_in))
                        text_in=text_in.strip()
                        if len(text_in)>3:
                            if text_in != text: 
                                #time.sleep(5)
                                text=text_in
                                if mutex_wrkrbusy.locked():
                                    mutex_wrkrbusy.release()
                                self.cond.wakeAll()
                                continue
                            else :
                                print("Cont. error")
                                tgr_cmd= [67]  #C
                                "".join(map(chr, tgr_cmd))
                                self.uart.write(tgr_cmd)
                                time.sleep(0.5)
                                if mutex_wrkrbusy.locked():
                                    mutex_wrkrbusy.release()
                        else :
                            print("Length error")
                            self.ser.flush()
                            tgr_cmd= [81]  #L
                            "".join(map(chr, tgr_cmd))
                            self.uart.write(tgr_cmd)
                            time.sleep(0.5)
                            if mutex_wrkrbusy.locked():
                                mutex_wrkrbusy.release()
                            
                    else:
                        #raise NameError("CMD ERR: "+ read_buf[0]+'|'+ read_buf[1]+'|'+  read_buf[2]+'|'+  read_buf[3]+'|'+ read_buf[4]+'|'+  read_buf[5]+'|'+  read_buf[6])
                        print("Serial QR command responce exception 1:")
                        print(e)
                        tgr_cmd= [81]  #Q
                        "".join(map(chr, tgr_cmd))
                        self.uart.write(tgr_cmd)
                        #raise NameError("CMD ERR: "+read_buf.hex())
                except Exception as e:
                    
                    print("Serial QR command responce exception 2:")
                    print(e)
                    time.sleep(8)
                    try :
                        self.ser = serial.Serial('/dev/qrscanner', baudrate=115200, timeout=5,
                                    parity=serial.PARITY_NONE,
                                    stopbits=serial.STOPBITS_ONE,
                                    bytesize=serial.EIGHTBITS
                                    )
                    except Exception as e:
                        print("Ser. init:"+datetime.now().strftime("%Y/%m/%d-%H:%M:%S"))
                        print(e)
                        self.signals.error_signal.emit('Inbuilt QR Reader not found! - '+str(e),'In-built QR Reader error')
                        time.sleep(255)
                        sys.exit()
                    tgr_cmd= [81]  #Q
                    "".join(map(chr, tgr_cmd))
                    self.uart.write(tgr_cmd)
                if mutex_wrkrbusy.locked():
                    mutex_wrkrbusy.release()
            except Exception as e:
                print("Serial QR loop exception:"+datetime.now().strftime("%Y/%m/%d-%H:%M:%S"))
                print(e)
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
                if mutex_wrkrbusy.locked():
                    mutex_wrkrbusy.release()
                self.signals.error_signal.emit("Serial QR loop exception:"+str(e),'In-built QR Reader error')
                if str(e)=="read failed: device reports readiness to read but returned no data (device disconnected or multiple access on port?)":
                    time.sleep(3)
                else:
                    time.sleep(255)
                sys.exit() 

class TimerThreadSignals(QObject):
    update_time=pyqtSignal()
    update_jigdetails=pyqtSignal()
    update_jigip=pyqtSignal()
    error_signal=pyqtSignal(str,str)

class TimerThread(QRunnable):
    def __init__(self, ui_in):
        super(TimerThread, self).__init__()
        self.signals = TimerThreadSignals() 
        self.uin=ui_in
    def run(self):
        global synch_serialthread
        self.signals.update_time.emit()
        self.signals.update_jigdetails.emit()
        self.signals.update_jigip.emit()
        loop2=1
        loop=0
        time.sleep(1)
        now=datetime.now()
        if now.year < 2021 or now.year > 2029:
            time.sleep(5)
            now=datetime.now()
            if now.year < 2021 or now.year > 2029:
                error_msg="Wrong date/time:"+datetime.now().strftime("%d/%m/%Y-%H:%M:%S")+"\nEnsure WiFi is connected and restart jig"
                self.signals.error_signal.emit(error_msg, 'Time/date error!')
                time.sleep(255)
                sys.exit()
        synch_serialthread=0
        while True:
            # Don't access UI elements directly from worker thread
            # self.uin.qr_input.setFocus()
            time.sleep(2)
            loop+=1
            if loop==30:
                self.signals.update_time.emit()
                #print('rrr\n')
                loop2+=1
                loop=0;
                if loop2==5:
                    loop2=0
                    self.signals.update_jigdetails.emit()
                    self.signals.update_jigip.emit()
          
class WorkerSignals(QObject):
    error_signal=pyqtSignal(str,str)
    change_value_matrix=pyqtSignal(str)
    change_value_cartridge=pyqtSignal(str)
    change_value_count=pyqtSignal(str)
    change_acceptvalue_count=pyqtSignal(str)
    change_rejectvalue_count=pyqtSignal(str)
    change_value_errors=pyqtSignal(str)           #self.update_time.emit()
            
class Worker(QRunnable):
    def __init__(self, mutex, cond,self_uart):
        global mutex_wrkrbusy
        super(Worker, self).__init__()
        self.signals = WorkerSignals()
        self.mtx = mutex
        self.cond = cond
        self.running=True
        self.uart=self_uart
        # New: persistent duplicate tracker (safe if module missing)
        try:
            self.duplicate_tracker = DuplicateTracker() if DuplicateTracker else None
        except Exception:
            self.duplicate_tracker = None
    def stop(self):
        self.running=False
        
        
    #def reset_clicked(self):   
    #    print("resetcount")
        #self.w.pushButton_2.clicked.connect(self.reset_clicked)   
        
        
    @pyqtSlot()
    def run(self):
        global line,cube,user, mutex_wrkrbusy
        global text
        prev_cat='-'
        prev_matrix='-'
        matrix='-'
        #count=0
        serial=0
        accno=0
        rejno=0
        #self.setupUi(self)
        #self.pushButton_2.clicked.connect(self.reset_clicked)
        
        self.matrix_db = sqlite3.connect(os.path.join(SCRIPT_DIR, 'scanner.db'))
        with open(os.path.join(SCRIPT_DIR, 'cat'), "r") as f2:
            f2.seek(0)
            cursor0 = self.matrix_db.cursor()
            cursor0.execute('''SELECT SEQ from sqlite_sequence WHERE name='cartridge';''')
            count=int(cursor0.fetchone()[0])-int(f2.read())
            self.signals.change_value_count.emit(str(count))
        with open(os.path.join(SCRIPT_DIR, 'matrix.txt'), "r") as f:
            f.seek(0)
            prev_matrix=matrix = f.read()
            self.signals.change_value_matrix.emit(matrix)
            
        with open(os.path.join(SCRIPT_DIR, 'Acc.csv')) as f3:
            sacc = mmap.mmap(f3.fileno(), 0, access=mmap.ACCESS_READ)
            #if s.find(b'PAS12211702610') != -1:
            #    print('True')
            
        with open(os.path.join(SCRIPT_DIR, 'Rej.csv')) as f3:
            srej = mmap.mmap(f3.fileno(), 0, access=mmap.ACCESS_READ)
            #if s.find(b'PAS12211702610') != -1:
            #    print('True')
                       
        while self.running:
            try:
                
                self.mtx.lock()
                #self.signals.change_value_count.emit("44")
                if mutex_wrkrbusy.locked():
                    mutex_wrkrbusy.release()
                self.cond.wait(self.mtx)
                mutex_wrkrbusy.acquire(blocking=False)
                self.mtx.unlock()
                #self.signals.change_value_count.emit("11")
                qr=text
                if qr[0] == matrixux.qr_id:
                    if qr == prev_matrix:
                        self.signals.change_value_errors.emit("Already scanned")
                        continue
                    #current_datetime=datetime.now().strftime("%Y/%m/%d-%H:%M:%S")
                    count=0
                    with open(os.path.join(SCRIPT_DIR, 'cat'), "w") as fc:
                        cursor4 = self.matrix_db.cursor()#
                        cursor4.execute('''SELECT SEQ from sqlite_sequence WHERE name='cartridge';''')
                        fc.write(str(cursor4.fetchone()[0])) 
                        cursor4.close()
                    prev_matrix=qr
                    if matrixux.qr_id =='M':
                        matrix=qr
                    else:
                        matrix=qr[1:]
                    with open(os.path.join(SCRIPT_DIR, 'matrix.txt'), "w") as f:
                        f.seek(0)
                        f.write(matrix)
                    ####api
                    self.signals.change_value_count.emit(str(count))
                    self.signals.change_value_matrix.emit(matrix)
                    continue 
                else: 
                    if len(qr) < 10:
                        self.signals.change_value_cartridge.emit('QR LENGTH ERROR') 
                        print ("Len error:"+qr)
                        continue
                    cursor5=self.matrix_db.cursor()
                    cursor5.execute('''SELECT EXISTS(SELECT * FROM (SELECT * FROM cartridge ORDER BY SERIAL DESC LIMIT 50) WHERE CARTRIDGE="'''+qr+'''" LIMIT 1);''')
                    repetQr=cursor5.fetchone()[0]
                    cursor5.close()
                    if repetQr==1:
                        continue

                    # New validation using modern logic (keeps UART/GPIO behavior)
                    try:
                        # Use global mould ranges loaded at startup
                        print(f"Validating QR: {qr}, Line: {line}, Batch: {batch_number}, Moulds: {len(_mould_ranges)}")
                        status, mould_name = handle_qr_scan(
                            qr,
                            line,
                            _mould_ranges,
                            duplicate_checker=(lambda code: self.duplicate_tracker.already_scanned(batch_number, code)) if self.duplicate_tracker and batch_number else None,
                        )
                        print(f"Validation result: {status}, Mould: {mould_name}")
                    except Exception as e:
                        print(f"Validation exception: {e}")
                        status, mould_name = ("OUT OF BATCH", None)

                    if status == "PASS":
                        # Accept path: log to DB (STATUS=1) same as legacy 'N' branch, then send 'A'
                        self.signals.change_acceptvalue_count.emit(str(accno))
                        accno+=1

                        try:
                            if self.duplicate_tracker and batch_number:
                                self.duplicate_tracker.record_scan(batch_number, qr)
                        except Exception:
                            pass

                        cursor2=self.matrix_db.cursor()
                        count+=1
                        current_datetime=datetime.now().strftime("%Y/%m/%d-%H:%M:%S")
                        sqlite_insert_with_param=str('''INSERT INTO cartridge VALUES ( ?, ?, ?, ?, ?, ?, ?);''')
                        data_tuple = (None,current_datetime,line,cube,matrix,qr,1)
                        cursor2.execute(sqlite_insert_with_param, data_tuple)
                        cursor2.close()

                        # Show QR with mould type
                        display_text = f"{qr} ({mould_name})" if mould_name else qr
                        self.signals.change_value_cartridge.emit(display_text)
                        self.signals.change_value_count.emit(str(count))
                        cursor3=self.matrix_db.cursor()
                        cursor3.execute("SELECT  max(rowid) FROM cartridge")
                        MaxRowNo = int(cursor3.fetchone()[0])
                        cursor3.execute("SELECT  min(rowid) FROM cartridge")
                        MinRowNo = int(cursor3.fetchone()[0])
                        if((MaxRowNo-MinRowNo)>500000) :
                            cursor3.execute("Delete from cartridge where rowid="+str(MinRowNo))
                        cursor3.close()
                        self.matrix_db.commit()

                        tgr_cmd= [65] # 'A'
                        "".join(map(chr, tgr_cmd))
                        if self.uart:
                            print(f"Sending ACCEPT command 'A' (65) to UART for QR: {qr}")
                            time.sleep(0.1)  # Small delay to ensure PIC is in wait_for_qr()
                            self.uart.write(tgr_cmd)
                            self.uart.flush()
                            print(f"  → UART flushed, 'A' sent")
                        else:
                            print("UART not available - cannot send accept command")

                    else:
                        # Reject path for DUPLICATE/INVALID/LINE MISMATCH/OUT OF BATCH
                        self.signals.change_rejectvalue_count.emit(str(rejno))
                        rejno+=1
                        
                        # Show error status
                        self.signals.change_value_cartridge.emit(f"{status}: {qr}")
                        
                        tgr_cmd= [82]  # 'R'
                        "".join(map(chr, tgr_cmd))
                        if self.uart:
                            print(f"Sending REJECT command 'R' (82) to UART for QR: {qr}, Reason: {status}")
                            time.sleep(0.1)  # Small delay to ensure PIC is in wait_for_qr()
                            self.uart.write(tgr_cmd)
                            self.uart.flush()
                            print(f"  → UART flushed, 'R' sent")
                        else:
                            print("UART not available - cannot send reject command")
                        
                    #self.signals.change_value_count.emit("33")
            except Exception as e:
                self.signals.change_value_cartridge.emit('** ERROR **')
                print("Exception:"+datetime.now().strftime("%Y/%m/%d-%H:%M:%S"))
                print(e)
                tgr_cmd= [76] #L
                "".join(map(chr, tgr_cmd))
                if self.uart:
                    self.uart.write(tgr_cmd)
                if mutex_wrkrbusy.locked():
                    mutex_wrkrbusy.release()
                self.signals.error_signal.emit("Worker exception:"+str(e),'Data logging error!')
                time.sleep(255)
                sys.exit()
        self.matrix_db.commit()
        self.matrix_db.close()
        

  


if __name__ == "__main__":
    import sys
    print("=== SCANNER App Starting ===")
    print(f"Python: {sys.version}")
    print(f"PyQt5 imported: OK")
    
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
        sys.exit(1)

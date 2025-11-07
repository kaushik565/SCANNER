#!/bin/env python
from datetime import datetime
import time
import socket
import logging
import os, glob
hn = socket.gethostname()
a = hn[:4]
now = time.time()
dt = str(datetime.now())
date = dt[:10]
criticalTime = now + 10 * 86400
for item in glob.glob(os.path.join('/SCANNER/LOGS/', '*.log')):
    itemTime = os.stat(item).st_mtime
    if len(item) == 41:
        if itemTime < criticalTime:
            os.remove(item)
logging.basicConfig(filename="/SCANNER/LOGS/{}_request[{}].log".format(a, date), level=logging.INFO, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
try:
    import requests
    import json
    import simplejson
    import time
    import sqlite3
    from threading import Thread
    import subprocess
    import sys
    loginurl = 'https://www.micropcr.in:3000/v1/proddevices/login'
    pingurl = 'https://www.micropcr.in:3000/v1/heartbeatdetails/'
    MXSR = "https://www.micropcr.in:3000/v1/matrixscanner"
    UWSR = "https://www.micropcr.in:3000/v1/ultrasonicscanner"
    DCMS = "https://www.micropcr.in:3000/v1/dcmcoatingscanner"
    FQCS = "https://www.micropcr.in:3000/v1/finalqcscanner"
    CPSR = "https://www.micropcr.in:3000/v1/cartridgepackingscanner"
    DMSR = "https://www.micropcr.in:3000/v1/dumpassemblyscanner"
    RWSR = "https://www.micropcr.in:3000/v1/reworkcartridgescanner"
    uploadurl = globals()[a]
    try:
        import pandas as pd
    except ImportError:
        while True:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", 'pandas'])
            except subprocess.CalledProcessError:
                continue
            break
    finally:
        import pandas as pd
    def dbcon():
        con = sqlite3.connect("/SCANNER/scanner.db")
        return con
    def login():
        post_fields = {"username": "userdemo", "password": "demo12"}
        response = requests.post(loginurl, data=post_fields)
        crfl = response.json()
        with open('/SCANNER/crlf.json', 'w') as f:
            json.dump(crfl, f)
        rs = response.content.decode()
        response = json.loads(rs)
    def tkn():
        with open('/SCANNER/crlf.json') as f:
            rs = json.load(f)
        if rs['success'] is True:
            token = rs["token"]
            return token
    def upload():
        global boom
        token = tkn()
        con = dbcon()
        boom = 1200
        df = pd.read_sql_query("SELECT * from cartridge where STATUS=1", con)
        if df.empty is False:
            for i in range(0, len(df)):

                payload = {"line": '{}'.format(df.iloc[i, 2]),
                           "cube": '{}'.format(df.iloc[i, 3]),
                           "matrix_qrcode": '{}'.format(df.iloc[i, 4]),
                           "cartridge_qrcode": '{}'.format(df.iloc[i, 5]),
                           "date_time": '{}'.format(df.iloc[i, 1]),
                           'Equipment_id': '{}'.format(hn[:11]),
                           'Site_code': '{}'.format(hn[11:13])
                           }
                try:
                    logging.info(payload)
                    response = requests.put(uploadurl,
                                            json=payload,
                                            headers={"Content-Type": "application/json",
                                                     "Authorization": "{}".format(token)})
                    logging.info(response)
                    a = str(response)
                    if a[11:14] == "201":
                        print(response)
                        print(response.text)
                        con.execute("UPDATE cartridge SET STATUS=0 WHERE SERIAL={}".format(df.iloc[i, 0]))
                        con.commit()
                    if response.text == "Unauthorized":
                        login()
                        token = tkn()
                        logging.info(payload)
                        response = requests.put(uploadurl,
                                                json=payload,
                                                headers={"Content-Type": "application/json",
                                                          "Authorization": "{}".format(token)})
                        logging.info(response)
                        a = str(response)
                        if a[11:14] == "201":
                            print(response.json()['success'])
                            print(response)
                            print(response.text)

                            con.execute("UPDATE cartridge SET STATUS=0 WHERE SERIAL={}".format(df.iloc[i, 0]))
                            con.commit()
                except UnboundLocalError:
                    pass
                except requests.exceptions.ConnectionError:
                    boom = 600
            else:
                print("no data founf in database")
        con.close()
    def ping():
        global boom1
        token = tkn()
        boom1 = 600
        data_get = {'Equipment_id': '{}'.format(hn[:11]),
                    'Site_code': '{}'.format(hn[11:13])
                    }
        try:
            response = requests.post(pingurl,
                                     json=data_get,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "{}".format(token)})
            if response.text == "Unauthorized":
                login()
                token = tkn()
                response = requests.post(pingurl,
                                         json=data_get,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "{}".format(token)})
            else:
                pass
            a = str(response)
            if a[11:14] == "201":
                print(response)
                print(response.text)
        except requests.exceptions.ConnectionError:
            boom1 = 300
        except UnboundLocalError:
            pass
    def ping1():
        print("===============pinging the server==================")
        try:
            ping()
        except FileNotFoundError:
            login()
            ping()
        except json.decoder.JSONDecodeError:
            login()
            ping()
        except simplejson.errors.JSONDecodeError:
            login()
            ping()
    def upload1():
        print("====================uploading====================")
        try:
            upload()
        except FileNotFoundError:
            login()
            upload()
        except json.decoder.JSONDecodeError:
            login()
            upload()
        except simplejson.errors.JSONDecodeError:
            login()
            ping()
    def up():
        while True:
            upload1()
            time.sleep(boom)
    def pi():
        while True:
            ping1()
            time.sleep(boom1)
    def main():
        up2 = Thread(target=up)
        pi2 = Thread(target=pi)
        up2.start()
        pi2.start()
    main()
except Exception as e:
    logging.exception(str(e))

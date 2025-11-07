#!/bin/env python
import requests
import json
import simplejson
import time
import sqlite3
import socket
from threading import Thread
import subprocess
import sys
import logging

logging.basicConfig(filename='/SCANNER/LOGS/mxsr_request.log', level=logging.INFO, format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

"""
loginurl = 'https://www.micropcr.in:3000/v1/proddevices/login'
uploadurl = 'https://www.micropcr.in:3000/v1/ultrasonicscanner/'
pingurl = 'https://www.micropcr.in:3000/v1/heartbeatdetails/'

"""
loginurl = 'https://www.micropcr.in:3000/v1/proddevices/login'
uploadurl = 'https://www.micropcr.in:3000/v1/matrixscanner/'
pingurl = 'https://www.micropcr.in:3000/v1/heartbeatdetails/'



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


# function to login and create a json file to store the response
def login():
    post_fields = {"username": "userdemo", "password": "demo12"}
    response = requests.post(loginurl, data=post_fields)
    crfl = response.json()
    with open('/SCANNER/crlf.json', 'w') as f:
        json.dump(crfl, f)
    rs = response.content.decode()
    response = json.loads(rs)


# function to extract the token from the response saved in the
# json file created by login function
def tkn():
    with open('/SCANNER/crlf.json') as f:
        rs = json.load(f)
    if rs['success'] is True:
        token = rs["token"]
        return token
    else:
        pass


# function to takeout data from db and convert it to the json format and upload
def upload():
    global boom
    token = tkn()
    # uploading data to server
    con = dbcon()
    boom = 1200
    hn = socket.gethostname()
    # open databse
    df = pd.read_sql_query("SELECT * from cartridge where STATUS=1", con)
    print(df)
    if df.empty is False:
        print(df)

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
                print(response.json()['success'])
                print(response)
                print(response.text)

                if (response.json()['success']) is True:
                    con.execute("UPDATE cartridge SET STATUS=0 WHERE SERIAL='{}'".format(df.iloc[i, 0]))
                    con.commit()
                else:
                    pass

            except requests.exceptions.ConnectionError:
                boom = 600
                pass
            except UnboundLocalError:
                pass

            try:
                if response.text == "Unauthorized":
                    login()
                    # login.main()
                    tokn2 = tkn()
                    logging.info(payload)
                    response = requests.put(uploadurl,
                                             json=payload,
                                             headers={"Content-Type": "application/json",
                                                      "Authorization": "{}".format(tokn2)})
                    logging.info(response)
                    print(response.json()['success'])
                    print(response)
                    print(response.text)
                    if (response.json()['success']) is True:
                        con.execute("UPDATE cartridge SET STATUS=0 WHERE SERIAL='{}'".format(df.iloc[i, 0]))
                        con.commit()
                    else:
                        pass

                else:
                    pass

                print("upload successful>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
            except UnboundLocalError:
                pass
            except requests.exceptions.ConnectionError:
                boom = 600
                pass
    else:
        pass
    con.close()


# function to ping the server with equipment and site id for verification
def ping():
    global boom1
    token = tkn()
    boom1 = 600
    hn = socket.gethostname()
    data_get = {'Equipment_id': '{}'.format(hn[:11]),
                'Site_code': '{}'.format(hn[11:13])
                }

    # Making a get request
    try:
        response = requests.post(pingurl,
                                 json=data_get,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "{}".format(token)})
        if response.text == "Unauthorized":
            login()
            # login.main()
            tokn2 = tkn()
            response = requests.post(pingurl,
                                     json=data_get,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "{}".format(tokn2)})
        else:
            pass
        print(response)
        print(response.text)
        print("pinging successful>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    except requests.exceptions.ConnectionError:
        boom1 = 300
        pass

    except UnboundLocalError:
        pass


# function to schedule function ping with exception
def ping1():
    print("<<<<<<<<<<<<<<<<<<<<<<<<<<pinging the server>>>>>>>>>>>>>>>>>>>>>>")
    print("_________________________________________________________")
    try:
        # upload()
        ping()

        # if the json file which contains response from where token has to be
        # extracted is not available or not created FNFE exception occurs
    except FileNotFoundError:
        login()
        # upload()
        ping()
        # if the json file is empty below exception has to be executed
    except json.decoder.JSONDecodeError:
        login()
        # upload()
        ping()
    except simplejson.errors.JSONDecodeError:
        login()
        upload()


def upload1():
    print("<<<<<<<<<<<<<<<<<<<<<<<<<<uploading data>>>>>>>>>>>>>>>>>>>>>>>>>>")
    print("__________________________________________________________________")
    try:
        upload()
        # if the json file which contains response from where token has to be
        # extracted is not available or not created FNFE exception occurs
    except FileNotFoundError:
        login()
        upload()

        # if the json file is empty below exception has to be executed
    except json.decoder.JSONDecodeError:
        login()
        upload()
    except simplejson.errors.JSONDecodeError:
        login()
        upload()


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

"""
payload = {"line": '{}'.format(df.iloc[i, 2]),
           "cube": '{}'.format(df.iloc[i, 3]),
           "matrix_qrcode": '{}'.format(df.iloc[i, 4]),
           "cartridge_qrcode": '{}'.format(df.iloc[i, 5]),
           "date_time": date_time_obj,
           'Equipment_id': '{}'.format(hn[:11]),
           'Site_code': '{}'.format(hn[11:13])

           }
           """
"""data_get = {'Equipment_id': '{}'.format(hn[:11]),
            'Site_code': '{}'.format(hn[11:13])}
            """

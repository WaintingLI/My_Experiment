'''
測試交易
'''
import time
import json
from datetime import datetime
import sys
import os
import configparser
import requests 
import shutil
from bs4 import BeautifulSoup
import pandas as pd
from pandas.core.frame import DataFrame
import talib
import logging
from binance.um_futures import UMFutures
from binance.lib.utils import config_logging
from binance.error import ClientError

#宣告金鑰
#申請的API KEY
API_KEY = "99f8e52284b5231ec02ecf51427d6ba8f0cb35ccd6473a0e10dc76ec4ddd39cc"

#申請的SECRaET_KEY
SECRET_KEY = "a4d932926c968f0af095e839299872c664e97d074744b6b9b154f250a0fe4928"

#BASE_URL = "https://fapi.binance.com"
BASE_URL = "https://testnet.binancefuture.com"


um_futures_client = UMFutures(
    key=API_KEY,
    secret=SECRET_KEY,
    base_url = BASE_URL
)

config_logging(logging, logging.INFO)

def get_balance() -> int:
    try:
        timestamp_2 = int(time.time()*1000)
        print(timestamp_2)
        response = um_futures_client.balance(recvWindow=6000)
        logging.debug(response)
        for i in range(1,len(response)):
            if response[i].get('asset') == 'USDT':
                wallet = response[i].get('balance')
                break
        return wallet
        
    except ClientError as error:
        logging.error(
            "Found error. status: %s,error code: %s, error message: %s", \
                error.status_code, error.error_code, error.error_message
        )
        


if __name__ == "__main__": 

    print(um_futures_client.base_url)
    timestamp_2 = int(time.time()*1000)
    print(timestamp_2)
    #response = um_futures_client.account()
    '''
    response = um_futures_client.balance(recvWindow=6000,assetl='USDT')
    print(type(response))
    print(response)
    print("=====================================================")
    for item in response:
        print(item)
    '''
    print("wallet =",get_balance())
    
    
    
   
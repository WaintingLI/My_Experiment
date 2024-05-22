'''
測試交易
'''
import time
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
API_KEY = "申請的API KEY"
SECRET_KEY = "申請的SECRET_KEY"

BASE_URL = "https://fapi.binance.com"


Kline_column = [
        'open_time',
        'open',
        'high',
        'low',
        'close',
        'volumn',
        'close_time',
        'turnover',
        'number',
        'active_buy_vol',
        'active_buy_turnover',
        'ignore'
    ]

time_sec={
    '1m':60,
    '5m':300,
    '15m':900,
    '30m':1800,
    '1h':3600,
    '2h':7200,
    '4h':14400,
    '6h':21600,
    '8h':28800,
    '1d':86400
    }

#切換命令提示字元到Python檔案所在的目錄
#檢查當前工作路徑是否在Python檔案的所在地,如果是就不會切換目錄
if os.path.dirname(sys.argv[0]):
    os.chdir(os.path.dirname(sys.argv[0]))


def get_price(symbol:str="BTCUSDT")->str:
    """_summary_
    獲取幣安對應貨幣的當前價格
    Args:
        symbol (str): 貨幣,ex:BTCUSDT

    Returns:
        str: 貨幣價格
    """
    try:
        price = UMFutures().ticker_price(symbol)["price"]
        return price
    except ClientError as error:
        logging.error(
            "Found error. status: %s,error code: %s, error message: %s", \
                error.status_code, error.error_code, error.error_message
            )
        
        return 0
    
def get_kline(symbol:str="BTCUSDT", interval:str="1d", start_time:int=1546272000000, end_time:int=1715731200000, limit:int = 500)->str:
    """_summary_
    獲取K線
    Args:
        symbol (str, optional): 選取幣種. Defaults to "BTCUSDT".
        interval (str, optional): k線圖以哪種時間間格. Defaults to "1d".
        limit (int, optional): 要取多少筆資料,最大值為1500. Defaults to 1.

    Returns:
        str: _description_
    """
    if limit > 1500:
        print("由於當前 limit =",limit,"大於1500,將強制設定為1500")
        limit = 1500
    try:
        res = UMFutures().klines(symbol, interval, startTime =start_time, endTime =end_time, limit=limit)
        return res
    except ClientError as error:
        logging.error(
            "Found error. status: %s,error code: %s, error message: %s", \
                error.status_code, error.error_code, error.error_message
        )
        return 0
    

def cal_timestrip (stamp:str = "2019-01-01 0:0:0.0") -> float:
    """_summary_
    將日期轉成以毫秒微單位的時間戳章
    Args:
        stamp (_type_, optional): 輸入日期與時間. Defaults to "2019-01-01 0:0:0.0".

    Returns:
        float: 回傳時間戳章
    """
    print(stamp)
    datetime_obj = datetime.strptime(stamp, '%Y-%m-%d %H:%M:%S.%f')
    start_time = int(time.mktime(datetime_obj.timetuple())*1000.0+datetime_obj.microsecond/1000)
    return start_time

def get_history_kline(symbol:str="BTCUSDT", interval:str="1d", START_TIME:int=1546272000000, finish_end_time:int=1715731200000)->DataFrame:
    """_summary_
    可以收尋大於1500筆資料
    Args:
        symbol (str, optional): 貨幣. Defaults to "BTCUSDT".
        interval (str, optional): 以多少時間來做間隔. Defaults to "1d".
        START_TIME (int, optional): 開始時間. Defaults to 1546272000000.
        finish_end_time (int, optional): 結束時間. Defaults to 1715731200000.

    Returns:
        DataFrame: 回傳dataframe資料格式
    """
    END_TIME = START_TIME + time_sec.get(interval)*500*1000
    meta_dataframe = pd.DataFrame(get_kline(symbol, interval, start_time=START_TIME, end_time=END_TIME, limit=1500), columns=Kline_column )
    START_TIME = END_TIME
    while finish_end_time > START_TIME:
        END_TIME = START_TIME + time_sec.get(interval)*500*1000
        meta_dataframe_2 = pd.DataFrame(get_kline(symbol, interval, start_time=START_TIME, end_time=END_TIME, limit=1500), columns=Kline_column)
        meta_dataframe =pd.concat([meta_dataframe,meta_dataframe_2], ignore_index=True)
        START_TIME = END_TIME
    return meta_dataframe
    




if __name__ == "__main__":
    data = {
        'one' : [1 ,0 ,1 ,9 ,2],
        'two' : [4, 0, 4, 9, 3],
        'three' : [0, 2, 0, 0, 1],
        'four' : [1, 1, 1, 9, 2]
        }
    df = pd.DataFrame(data)
    print(df)
    print(df.drop_duplicates())
    #獲取所有Functions
    print(talib.get_functions())
    
    config_logging(logging, logging.INFO) #關閉debug顯示
    #關閉debug顯示 config_logging(logging, logging.DEBUG)
    #um_futures_client = UMFutures()
    #logging.info(um_futures_client.ticker_price("BTCUSDT"))
    price = UMFutures().ticker_price("BTCUSDT")["price"]
    print("BTC當前價格{}".format(price))
    #獲取K線圖
    
    #暫時先不開啟
    
    #KLine = pd.DataFrame(get_kline(limit=2000),columns=Kline_column)
    #print(KLine)
    
    print("datetime.now() =",datetime.now())
    print(time.time())
    SET_START_TIME = cal_timestrip("2019-01-01 0:0:0.0")
    print("SET_START_TIME=",SET_START_TIME)
    FINISH_TIME = cal_timestrip(str(datetime.now()))
    print("FINISH_TIME=",FINISH_TIME)
    KLine = pd.DataFrame(get_history_kline(START_TIME=SET_START_TIME, finish_end_time=FINISH_TIME),columns=Kline_column)
    print(KLine)
    KLine.to_csv("test.csv")

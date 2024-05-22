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
SECRET_KEY = "申請的SECRaET_KEY"

BASE_URL = "https://fapi.binance.com"


Kline_column = [
        'Open_time',
        'Open',
        'High',
        'Low',
        'Close',
        'Volumn',
        'Close_time',
        'Turnover',
        'Number',
        'Active_buy_vol',
        'Active_buy_turnover',
        'Ignore'
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

def get_history_kline(symbol:str="BTCUSDT",
                      interval:str="1d",
                      START_TIME:int=1546272000000,
                      finish_end_time:int=1715731200000)->DataFrame:
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
    meta_dataframe['Open_time'] = pd.to_datetime(meta_dataframe['Open_time'], unit='ms')
    meta_dataframe['Close_time'] = pd.to_datetime(meta_dataframe['Close_time'], unit='ms')
    return meta_dataframe



def pre_processing(ohlcv:DataFrame) -> DataFrame:
    """_summary_
    將歷史資料丟進來,進行布林帶值轉換後再丟出
    Args:
        ohlcv (DataFrame): 歷史資料

    Returns:
        DataFrame: 經過布林帶值轉換的資料
    """
    kline_data = pd.DataFrame()
    #將開盤時間存入
    kline_data['data_time'] = ohlcv['Open_time']
    #計算布林帶值
    kline_data['ub'], kline_data['boll'], kline_data['lb'] = \
        talib.BBANDS(ohlcv['Close'],
                     timeperiod=22,
                     nbdevup=2.0,
                     nbdevdn=2.0
                     )
    #設定buy_sell欄位為空值
    kline_data['buy_sell'] = ''
    #寫入收盤價
    kline_data['price'] = ohlcv['Close']
    
    #讀取資料
    for i in range(1,len(kline_data)):
        price = float(kline_data.loc[i,'price'])
        ub = float(kline_data.loc[i,'ub'])
        boll = float(kline_data.loc[i,'boll'])
        lb = float(kline_data.loc[i,'lb'])
        
        if price > (ub-(ub-boll)/5):
            kline_data.loc[i,'buy_sell'] = 'SELL'
        elif price > (lb+(boll-lb)/5):
            kline_data.loc[i,'buy_sell'] = 'BUY'
    
    return kline_data

def back_test_para(k_line_data:DataFrame) -> float:
    #1. 宣告變數 -- 開單訊息
    #交易旗標,場上是否存在交易
    trade_flag = False
    #開單時間
    open_time = ''
    #開單方向
    open_time_direction = ''
    #開單價格
    open_price = 0.0
    
    #2. 宣告變數 -- 資金/倉位
    #初始資金
    start_finance = 10000.00
    #倉位管理以100為單位,每100下0.01張
    trade_num = int(start_finance/100)*0.01
    
    #3. 宣告變數 -- 手續費
    open_fee = 0.0
    close_fee = 0.0
    
    #正式流程
    for i in range(1,len(k_line_data)):
        # 先取得當前索引價格
        now_price = float(k_line_data.loc[i,'price'])
        #未開單情況
        if not trade_flag:
            #當open_time_direction為'',且buy_sell不為0時,依buy_sell進行買入設定
            if open_time_direction == '':
                if k_line_data.loc[i,'buy_sell'] != '':
                    #紀錄開單資訊
                    open_time = k_line_data.loc[i,'data_time']
                    open_price = now_price
                    open_time_direction = k_line_data.loc[i,'buy_sell']
                    #更改為場上有單
                    trade_flag = True
                    #計算開單手續費
                    open_fee = open_price*trade_num*0.0004
        #場上已開單
        if trade_flag:
            #判斷開單方向
            if open_time_direction == 'BUY':
                #判斷當前價格是否大於開單價格達20點以上
                if now_price - open_price > 20:
                    #大於20點以上進行平單處理 - 平單手續費計算
                    close_fee = (now_price * trade_num*0.0002)
                    #計算淨利
                    profit = ((now_price - open_price)*trade_num) - open_fee - close_fee
                    #變數重置
                    open_time_direction = ''
                    open_time = ''
                    open_price = 0.0
                    #淨利和初始資金進行加總
                    start_finance = start_finance + profit
                    #依變動後的資金重新計算下次開單的張數
                    trade_num = int(start_finance / 100) *0.01
                    #重新設置交易旗標為False,場上無單
                    trade_flag = False
                elif now_price - open_price < -20:
                    #虧20點以上進行平單處理 - 平單手續費計算
                    close_fee = (now_price * trade_num*0.0002)
                    #計算淨利
                    profit = ((now_price - open_price)*trade_num) - open_fee - close_fee
                    #變數重置
                    open_time_direction = ''
                    open_time = ''
                    open_price = 0.0
                    #淨利和初始資金進行加總
                    start_finance = start_finance + profit
                    #依變動後的資金重新計算下次開單的張數
                    trade_num = int(start_finance / 100) *0.01
                    #重新設置交易旗標為False,場上無單
                    trade_flag = False
            elif open_time_direction == 'SELL':
                #判斷當前價格是否大於開單價格達20點以上
                if now_price - open_price > 20:
                    #大於20點以上進行平單處理 - 平單手續費計算
                    close_fee = (now_price * trade_num*0.0002)
                    #計算淨利
                    profit = ((now_price - open_price)*trade_num) - open_fee - close_fee
                    #變數重置
                    open_time_direction = ''
                    open_time = ''
                    open_price = 0.0
                    #淨利和初始資金進行加總
                    start_finance = start_finance + profit
                    #依變動後的資金重新計算下次開單的張數
                    trade_num = int(start_finance / 100) *0.01
                    #重新設置交易旗標為False,場上無單
                    trade_flag = False
                elif now_price - open_price < -20:
                    #虧20點以上進行平單處理 - 平單手續費計算
                    close_fee = (now_price * trade_num*0.0002)
                    #計算淨利
                    profit = ((now_price - open_price)*trade_num) - open_fee - close_fee
                    #變數重置
                    open_time_direction = ''
                    open_time = ''
                    open_price = 0.0
                    #淨利和初始資金進行加總
                    start_finance = start_finance + profit
                    #依變動後的資金重新計算下次開單的張數
                    trade_num = int(start_finance / 100) *0.01
                    #重新設置交易旗標為False,場上無單
                    trade_flag = False
    return start_finance


if __name__ == "__main__":
    #獲取所有Functions print(talib.get_functions())
    
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

    #回測時間設定
    #當前時間
    print("datetime.now() =",datetime.now())
    print(time.time())
    #SET_START_TIME = cal_timestrip("2019-01-01 0:0:0.0")
    SET_START_TIME = cal_timestrip("2019-01-01 0:0:0.0")
    print("SET_START_TIME=",SET_START_TIME)
    FINISH_TIME = cal_timestrip(str(datetime.now()))
    print("FINISH_TIME=",FINISH_TIME)
    #獲取K線資料
    KLine = pd.DataFrame(get_history_kline(START_TIME=SET_START_TIME, finish_end_time=FINISH_TIME),columns=Kline_column)
    print(KLine)
    
    #將K線資料進行布林帶值的轉換,並且獲取該資料
    get_back_test_data = pre_processing(KLine)
    print(get_back_test_data)
    get_back_test_data.to_xml("test.xml")
    get_back_test_data.to_csv("test.csv")
    print("初始資金:10000")
    print("回測結果=",back_test_para(get_back_test_data))

    

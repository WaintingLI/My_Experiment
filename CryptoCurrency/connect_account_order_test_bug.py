'''
測試交易
'''
import time
import json
from datetime import datetime
import sys
import os
import configparser
import shutil
import logging
import traceback
import requests
from bs4 import BeautifulSoup
import pandas as pd
from pandas.core.frame import DataFrame
import talib

from binance.um_futures import UMFutures
from binance.lib.utils import config_logging
from binance.error import ClientError

#幣安測試平台宣告金鑰
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


#設定交易對
SYMBOL = 'BTCUSDT'




#取得USDT錢包
def get_balance(symbol:str = 'USDT') -> str|None:
    """獲取當前的資金餘額
    Args:
        symbol (str): 找尋資產類別,如USDT

    Returns:
        str: 回傳資金餘額
    """
    try:
        response = um_futures_client.balance(recvWindow=6000)
        logging.debug(response)
        for i in range(1,len(response)):
            if response[i].get('asset') == symbol:
                wallet = response[i].get('balance')
                break
        return wallet

    except ClientError as error:
        logging.error(
            "Found error. status: %s,error code: %s, error message: %s", \
                error.status_code, error.error_code, error.error_message
        )
        traceback.print_stack()
        return None

#取得K線圖資料
def get_kline(symbol:str="BTCUSDT", interval:str="1d", limit:int = 500)->str:
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
        res = um_futures_client.klines(symbol, interval, limit=limit)
        return res
    except ClientError as error:
        logging.error(
            "Found error. status: %s,error code: %s, error message: %s", \
                error.status_code, error.error_code, error.error_message
        )
        traceback.print_stack()
        return 0

#取得即時價格
def get_price(symbol:str="BTCUSDT")->float|None:
    """
    獲取幣安對應貨幣的當前價格
    Args:
        symbol (str, optional): 貨幣. Defaults to "BTCUSDT".

    Returns:
        float|None: 貨幣價格,如果輸入錯誤會回傳0
    """
    try:
        price = float(um_futures_client.ticker_price(symbol)["price"])
        return price
    except ClientError as error:
        logging.error(
            "Found error. status: %s,error code: %s, error message: %s", \
                error.status_code, error.error_code, error.error_message
            )
        traceback.print_stack()
        return 0

# 下單/平單 函式
def new_order(order_symbol:str, order_side:str, order_quantity:float) -> int:
    try:
        response = um_futures_client.new_order(
            symbol=order_symbol,
            side=order_side,
            type="MARKET",
            quantity=order_quantity
        )
        logging.debug(response)
        return response['orderId']
    except ClientError as error:
        logging.error(
            "Found error. status: %s, error code: %s, error message: %s", \
                error.status_code, error.error_code, error.error_message
        )
        traceback.print_stack()
        return 0

#取得訂單內容及回傳交易價格
def get_order(order_symbol:str, order_orderid:int) -> list:
    """_summary_
    透過幣種與訂單編號,來查詢訂單資訊
    Args:
        order_symbol (str): 幣種
        order_orderid (int): 訂單編號

    Returns:
        list: 如果有找到訂單,則回傳訂單資訊;如果沒有則回傳 0
    """
    try:
        response = um_futures_client.get_all_orders(
            symbol=order_symbol,
            orderId=order_orderid,
            recvWindow=2000)
        logging.debug(response)
        return float(response[0]['avgPrice'])
    except ClientError as error:
        logging.error(
            "Found error. status: %s, error code: %s, error message: %s", \
                error.status_code, error.error_code, error.error_message
        )
        traceback.print_stack()
        return 0


# 從K線資料中讀取資料
def read_data_frome_kline(data:DataFrame,i:int) -> float:
    """_summary_
    用來讀取k,d,j指標與atr指標的計算資料後,所得到的參數
    Args:
        data (DataFrame): 要透過指標計算的資料
        i (int): 第幾列的資料

    Returns:
        float: 各指標回傳的計算結果
    """
    k = float(data.loc[i,'k'])
    d = float(data.loc[i,'d'])
    j = float(data.loc[i,'j'])
    now_atr = float(data.loc[i,'atr'])
    pre_atr = float(data.loc[i - 1,'atr'])
    new_price = float(data.loc[i,'price'])
    pre_price = float(data.loc[i - 1,'price'])
    return k, d, j, now_atr, pre_atr, new_price, pre_price

# 指標計算
def indicator_cal() -> str | DataFrame:
    """_summary_
    讀取當前幣安上面的資料,並且計算指標
    Returns:
        str | DataFrame: 回傳 "BUY" or "SELL";回傳經過指標計算的資料
    """
    #創造一個空的
    kline_data = pd.DataFrame()
    #從幣安獲取N根k棒
    ohlcv = pd.DataFrame(get_kline(SYMBOL,'1m',50),columns=[
        'Timestamp',
        'Open',
        'High',
        'Low',
        'Close',
        'Volumn',
        'Close_time',
        'Quote_av',
        'Trades',
        'tb_base_av',
        'tb_quote_av',
        'Ignore'
    ])

    #計算K、D、J值
    kline_data['date_time'] = ohlcv['Timestamp']
    kline_data['k'], kline_data['d'] = talib.STOCH(
        ohlcv['High'],
        ohlcv['Low'],
        ohlcv['Close'],
        fastk_period = 9,
        slowk_period = 3,
        slowd_period = 3
    )
    kline_data['j'] = 3 * kline_data['k'] - 2 * kline_data['d']
    kline_data['price'] = ohlcv['Close']

    #計算ATR值
    kline_data['atr'] = talib.ATR(
        ohlcv['High'],
        ohlcv['Low'],
        ohlcv['Close'],
        timeperiod=14
    )

    k, d, j, now_atr, pre_atr, new_price, pre_price = \
        read_data_frome_kline(kline_data, 48)
    buy_sell = ''

    if (new_price - pre_price) / pre_price > (now_atr - pre_atr) / pre_atr and (now_atr > pre_atr):
        if (j < k) and (k < d) and (j < 40):
            buy_sell = 'BUY'
    elif (pre_price - new_price) / new_price > (pre_atr - now_atr) / now_atr and (now_atr < pre_atr):
        if (j > k) and (k > d) and (j > 60):
            buy_sell = 'SELL'
    return buy_sell, kline_data

# 報告書出
def report_csv():
    return 0

if __name__ == "__main__": 
    print("wallet =",get_balance('USDT'))
    
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
    start_finance = float(get_balance('USDT'))
    print("初始資金 =",start_finance)
    
    #倉位管理以100為單位,每100下0.01張(要購買幣種的數量)
    trade_num = int(start_finance/100)*0.01
    print("倉位管理=",trade_num)
    
    #3. 宣告變數 -- 手續費
    open_fee = 0.0
    close_fee = 0.0
    
    #補單次數
    dup_time = 0
    #獲利延伸
    dup_profit = 1
    
    #order_id = new_order(SYMBOL,'SELL',0.01)
    #表示訂單編號
    order_id = 0
    #print("order_id =",order_id,type(order_id))
    #order_id_test=4037481497
    #print("order_id_test =",order_id_test)
    #get_order_data = get_order(SYMBOL,order_id)
    #print("get_order_data =",get_order_data)
    #print(type(get_order_data))
    
    old_time = 0.0
    open_time_direction, kline_data = indicator_cal()
    open_time_direction = 'BUY'
    trade_num = 9
    now_price = get_price(SYMBOL)
    open_time = datetime.now()
    order_id = new_order(SYMBOL, open_time_direction, trade_num)
    print("order_id =",order_id)
    open_price = get_order(SYMBOL, order_id)
    trade_flag = True
    open_fee = open_price / 20 *trade_num * 0.0004
    print('開單日期{}, 開單價格{}, 開單數量{}, 開單手續費{}'.format(
        open_time, open_price, trade_num, open_fee))
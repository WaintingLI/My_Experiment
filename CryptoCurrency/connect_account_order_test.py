'''
測試交易
'''
import time
from datetime import datetime
import sys
import os
import configparser
import shutil
import traceback
import logging
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
#API_KEY = "99f8e52284b5231ec02ecf51427d6ba8f0cb35ccd6473a0e10dc76ec4ddd39cc"

#申請的SECRaET_KEY
#SECRET_KEY = "a4d932926c968f0af095e839299872c664e97d074744b6b9b154f250a0fe4928"

#BASE_URL = "https://fapi.binance.com"
#BASE_URL = "https://testnet.binancefuture.com"

#讀取config.ini
cf=configparser.ConfigParser()
cf.read_file(open('config.ini', 'r', encoding='UTF-8'))
API_KEY = cf.get("Binance_Setting","API_KEY")
SECRET_KEY = cf.get("Binance_Setting","SECRET_KEY")
BASE_URL = cf.get("Binance_Setting","BASE_URL")

#ADMIN_EMAIL = cf.get("APP_Info","Admin_E-Mail")
#獲取專案的名稱與設定
#PROJECT_NAME = cf.get("Project","Project_Name")
#PROJECT_KEY = cf.get("Project","Project_Key")





um_futures_client = UMFutures(
    key=API_KEY,
    secret=SECRET_KEY,
    base_url = BASE_URL
)

config_logging(logging, logging.INFO)

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

#設定交易對
SYMBOL = 'BTCUSDT'

#倒數十秒
def count_down_ten_seconds() -> None:
    """_summary_
    暫停倒數10秒,主要當連線失敗後,再等10秒後,再去連線
    """
    for i in range(10):
        time.sleep(1)
        print(i,"秒",end=" ")
    


#取得USDT錢包
def get_balance(symbol:str = 'USDT') -> str|None:
    """獲取當前的資金餘額
    Args:
        symbol (str): 找尋資產類別,如USDT

    Returns:
        str: 回傳資金餘額
    """
    while True:
        try:
            response = um_futures_client.balance(recvWindow=4000)
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
            count_down_ten_seconds()
            continue
        except requests.exceptions.SSLError:
            traceback.print_stack()
            count_down_ten_seconds()
            continue

#取得K線圖資料
def get_kline(symbol:str="BTCUSDT", interval:str="1d", limit:int = 500)->list:
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
    meta_dataframe = pd.DataFrame(UMFutures().klines(symbol, interval, startTime=START_TIME, endTime=END_TIME, limit=500), columns=Kline_column )
    START_TIME = END_TIME
    while finish_end_time > START_TIME:
        END_TIME = START_TIME + time_sec.get(interval)*500*1000
        meta_dataframe_2 = pd.DataFrame(UMFutures().klines(symbol, interval, startTime=START_TIME, endTime=END_TIME, limit=500), columns=Kline_column)
        meta_dataframe =pd.concat([meta_dataframe,meta_dataframe_2], ignore_index=True)
        START_TIME = END_TIME
    meta_dataframe['Open_time'] = pd.to_datetime(meta_dataframe['Open_time'], unit='ms')
    meta_dataframe['Close_time'] = pd.to_datetime(meta_dataframe['Close_time'], unit='ms')
    return meta_dataframe


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
        order_quantity = round(order_quantity, 8)
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
        print("Error new_order parameter: order_symbol=",order_symbol,"; order_side=",order_side,"; order_quantity=",order_quantity)
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
    #=========================================================================================================================
    '''
    #測試讀取歷史數據
    print("datetime.now() =",datetime.now())
    print(time.time())
    #SET_START_TIME = cal_timestrip("2019-01-01 0:0:0.0")
    SET_START_TIME = cal_timestrip("2019-01-01 0:0:0.0")
    print("SET_START_TIME=",SET_START_TIME)
    FINISH_TIME = cal_timestrip(str(datetime.now()))
    print("FINISH_TIME=",FINISH_TIME)
    #獲取K線資料    
    KLine = pd.DataFrame(get_history_kline(interval='1m',START_TIME=SET_START_TIME, finish_end_time=FINISH_TIME),columns=Kline_column)
    print(KLine)
    #將今天的日期作為輸出的檔案名稱
    tmp_date = datetime.today().strftime("%Y-%m-%d-%H-%M-%S")
    KLine.to_csv(f"{tmp_date}.csv")
    sys.exit(0)
    '''
    #=========================================================================================================================
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
    #無限迴圈
    while True:
        new_time = time.time()
        if int(new_time) % 60 == 0:
            old_time = new_time - 60
            print("old_time=",old_time,"; new_time=",new_time)
            break
    while True:
        if not trade_flag:
            new_time = time.time()
            if new_time - old_time >= 60:
                #判斷當前方向
                print("===========================================================")
                print('start_time = {}'.format(datetime.now()))
                open_time_direction, kline_data = indicator_cal()
                print('end_time = {}'.format(datetime.now()))
                print(datetime.now())
                if open_time_direction != '':
                    open_time = datetime.now()
                    order_id = new_order(SYMBOL, open_time_direction, trade_num)
                    #錯誤發生時,order_id = 0
                    if order_id == 0:
                        print("訂單失敗,跳過此次開單")
                        continue
                    open_price = get_order(SYMBOL, order_id)
                    trade_flag = True
                    open_fee = open_price / 20 *trade_num * 0.0004
                    print('開單日期{}, 開單價格{}, 開單數量{}, 開單手續費{}'.format(
                        open_time, open_price, trade_num, open_fee))
                old_time = new_time
                time.sleep(59)
        elif trade_flag:
            new_time = time.time()
            if new_time - old_time >= 60:
                #方向為BUY時
                now_price = get_price(SYMBOL)
                new_time = time.time()
                if new_time - old_time >= 60:
                    now_direction, kline_data = indicator_cal()
                    old_time = new_time
                else:
                    now_direction = open_time_direction
                if open_time_direction == 'BUY':
                    #止盈程式碼
                    if now_price - open_price > 120 * dup_profit:
                        if now_direction == '' or now_direction == 'SELL':
                            order_id = new_order(SYMBOL, 'SELL', trade_num)
                            close_price = get_order(SYMBOL, order_id)
                            close_fee = close_price / 20 *trade_num * 0.0002
                            open_fee = ''
                            dup_time = 0
                            open_time_direction = ''
                            open_time = ''
                            open_price = 0.0
                            dup_profit = 1
                            start_finance = float(get_balance('USDT'))
                            trade_num = int(start_finance / 100) * 0.01
                            trade_flag = False
                        else:
                            dup_profit += 1
                    #補倉程式碼, dup_time < 2 表示最多只補兩次
                    elif now_price - open_price < -100 * (dup_time + 1):
                        if dup_time < 2:
                            order_id = new_order(SYMBOL, open_time_direction, trade_num*2)
                            temp_price = get_order(SYMBOL, order_id)
                            open_price = (open_price + temp_price * 2) / 3
                            open_fee = open_fee + (temp_price / 20 * trade_num * 2 * 0.0002)
                            trade_num = trade_num + (trade_num * 2)
                            dup_time = dup_time + 1
                    #補倉後止盈
                    if dup_time >= 2:
                        if now_price - open_price > 50 * dup_profit:
                            if now_direction == '' or now_direction == 'SELL':
                                order_id = new_order(SYMBOL, 'SELL', trade_num)
                                close_price = get_order(SYMBOL, order_id)
                                close_fee = close_price / 20 *trade_num * 0.0002
                                open_fee = ''
                                dup_time = 0
                                open_time_direction = ''
                                open_time = ''
                                open_price = 0.0
                                dup_profit = 1
                                start_finance = float(get_balance('USDT'))
                                trade_num = int(start_finance / 100) * 0.01
                                trade_flag = False
                            else:
                                dup_profit += 1
                                
                elif open_time_direction == 'SELL':
                    #止盈程式碼
                    if open_price - now_price > 120 * dup_profit:
                        if now_direction == '' or now_direction == 'BUY':
                            order_id = new_order(SYMBOL, 'BUY', trade_num)
                            close_price = get_order(SYMBOL, order_id)
                            close_fee = close_price / 20 *trade_num * 0.0002
                            dup_time = 0
                            open_time_direction = ''
                            open_time = ''
                            open_price = 0.0
                            dup_profit = 1
                            start_finance = float(get_balance('USDT'))
                            trade_num = int(start_finance / 100) * 0.01
                            trade_flag = False
                    #補倉程式碼, dup_time < 2 表示最多只補兩次
                    elif open_price - now_price < -100 * (dup_time + 1):
                        if dup_time < 2:
                            order_id = new_order(SYMBOL, open_time_direction, trade_num*2)
                            temp_price = get_order(SYMBOL, order_id)
                            open_price = (open_price + temp_price * 2) / 3
                            open_fee = open_fee + (temp_price / 20 * trade_num * 2 * 0.0002)
                            trade_num = trade_num + (trade_num * 2)
                            dup_time = dup_time + 1
                    #補倉後止盈
                    if dup_time >= 2:
                        if open_price - now_price > 50 * dup_profit:
                            if now_direction == '' or now_direction == 'BUY':
                                order_id = new_order(SYMBOL, 'BUY', trade_num)
                                close_price = get_order(SYMBOL, order_id)
                                close_fee = close_price / 20 * trade_num * 0.0002
                                dup_time = 0
                                open_time_direction = ''
                                open_time = ''
                                open_price = 0.0
                                start_finance = float(get_balance('USDT'))
                                trade_num = int(start_finance / 100) * 0.01
                                trade_flag = False
                            else:
                                dup_profit += 1

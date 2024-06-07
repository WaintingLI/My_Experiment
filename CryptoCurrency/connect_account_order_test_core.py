'''
測試交易
'''
import time
from datetime import datetime
import sys
import os
import threading
from queue import Queue
from queue import Empty
import configparser
import shutil
import traceback
import logging
import requests
import pandas as pd
from pandas.core.frame import DataFrame
import talib
from binance.um_futures import UMFutures
from binance.lib.utils import config_logging
from binance.error import ClientError
from alive_progress import alive_bar
from PyQt6 import QtCore, QtGui, QtWidgets


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
SYMBOL = cf.get("Binance_Setting","SYMBOL")
#是否要開啟回測
#Virtual_flag = True
Virtual_flag = cf.getboolean("Simulation_back_test","Virtual_flag")
#Virtual_interval = "8h"
Virtual_interval = cf.get("Simulation_back_test","Virtual_interval")
#Virtual_total_funding = 0.0
Virtual_total_funding = cf.getfloat("Simulation_back_test","Virtual_total_funding")
Virtual_timer = 0

#存放歷史資料
History_KLine = pd.DataFrame()
#存放要匯出的資料
History_KLine_Export = pd.DataFrame()
#設定交易對
#SYMBOL = 'BTCUSDT'
#ADMIN_EMAIL = cf.get("APP_Info","Admin_E-Mail")
#獲取專案的名稱與設定
#PROJECT_NAME = cf.get("Project","Project_Name")
#PROJECT_KEY = cf.get("Project","Project_Key")

#虛擬倉位
Virtual_position_falg = False
Virtual_position = 0.0
Virtual_position_way = ""
Virtual_position_margin = 0.0
Virtual_position_open_price = 0.0
Virtual_position_trade_num = 0.0

#全域變數
print_message_queue = Queue

#需要主程式設定
Start_time_str = ""
End_time_str = ""

#給主執行緒提供的參數
#print_terminal = Queue()
#print_progress_bar = QtWidgets.QProgressBar
Force_stop_flag = False

#設定loging訊息
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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

class Progress_bar(threading.Thread):
    """_summary_
    用來顯示進度條
    Args:
        threading (_type_): 宣告種類
    """
    def __init__(self, queue:Queue, total_num:int):
        """_summary_
        宣告後立即會執行的東西
        Args:
            queue (Queue): 都進來的存列
            total_num (int): 總資料筆數
        """
        threading.Thread.__init__(self)
        self.queue = queue
        self.total_num = total_num

    def run(self):
        count = 0
        with alive_bar(self.total_num) as bar:
            print("讀取資料中")
            while True:
                try:
                    get_value = self.queue.get(timeout=10)
                    bar(get_value)
                    count += get_value
                    if count >= self.total_num:
                        break
                except Empty:
                    break


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
    global Virtual_flag
    global Virtual_total_funding
    if Virtual_flag:
        return str(Virtual_total_funding)
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
            if error.error_message == "API-key format invalid.":
                #print("API錯誤")
                return None
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
    global History_KLine
    global Virtual_timer
    global Virtual_flag
    if limit > 1500:
        print("由於當前 limit =",limit,"大於1500,將強制設定為1500")
        limit = 1500
    if Virtual_flag:
        if limit > Virtual_timer:
            Virtual_timer = limit
        temp_data = History_KLine.iloc[Virtual_timer - limit:Virtual_timer,:]
        return temp_data.values.tolist()
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
    data_queue = Queue()
    REAL_START_TIME = UMFutures().klines(symbol, interval, startTime=START_TIME, limit=1)[0][0]    
    REAL_finish_end_time = UMFutures().klines(symbol, interval,limit=1)[0][0]
    TOTAL_DATA_NUM = int((REAL_finish_end_time - REAL_START_TIME) / ( time_sec.get(interval)*1000)) + 1
    print("TOTAL_DATA_NUM =",TOTAL_DATA_NUM)
    END_TIME = START_TIME + time_sec.get(interval)*500*1000
    meta_dataframe = pd.DataFrame(UMFutures().klines(symbol, interval, startTime=START_TIME, endTime=END_TIME, limit=500), columns=Kline_column )
    process_bar = Progress_bar(data_queue,TOTAL_DATA_NUM)
    process_bar.daemon = True
    process_bar.start()
    if TOTAL_DATA_NUM <= 500:
        data_queue.put(TOTAL_DATA_NUM)
    else:
        data_queue.put(500)
        TOTAL_DATA_NUM -= 500
    START_TIME = END_TIME
    while finish_end_time > START_TIME:
        END_TIME = START_TIME + time_sec.get(interval)*500*1000
        meta_dataframe_2 = pd.DataFrame(UMFutures().klines(symbol, interval, startTime=START_TIME, endTime=END_TIME, limit=500), columns=Kline_column)
        meta_dataframe =pd.concat([meta_dataframe,meta_dataframe_2], ignore_index=True)
        START_TIME = END_TIME
        if TOTAL_DATA_NUM < 500:
            data_queue.put(TOTAL_DATA_NUM)
        else:
            data_queue.put(500)
            TOTAL_DATA_NUM -= 500
    process_bar.join()
    #將日期轉換成人演可辨識的
    #meta_dataframe['Open_time'] = pd.to_datetime(meta_dataframe['Open_time'], unit='ms')
    #meta_dataframe['Close_time'] = pd.to_datetime(meta_dataframe['Close_time'], unit='ms')
    
    #移除重複項目
    meta_dataframe.drop_duplicates(subset='Open_time',keep='first',inplace=True)
    #重新排序
    #meta_dataframe = meta_dataframe.reset_index(drop=True)
    return meta_dataframe.reset_index(drop=True)


def cal_timestrip (stamp:str = "2019-01-01 0:0:0.0") -> float:
    """_summary_
    將日期轉成以毫秒微單位的時間戳章
    Args:
        stamp (_type_, optional): 輸入日期與時間. Defaults to "2019-01-01 0:0:0.0".

    Returns:
        float: 回傳時間戳章
    """
    logging.debug(f"{stamp}")
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
    global History_KLine
    global Virtual_timer
    global Virtual_flag
    
    if Virtual_flag:
        price = History_KLine.loc[Virtual_timer,'Close']
        return float(price)
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
    global History_KLine
    global Virtual_timer
    global Virtual_flag
    global Virtual_total_funding
    if Virtual_flag:
        #計算開倉手續費
        temp_fee = int(float(History_KLine.loc[Virtual_timer,'Close']))*order_quantity*0.005
        margin = int(float(History_KLine.loc[Virtual_timer,'Close']))*order_quantity/20
        if Virtual_total_funding < (temp_fee + margin) or order_quantity <=0:
            History_KLine_Export.loc[Virtual_timer,'Position_Status'] = "開倉失敗"
            History_KLine_Export.loc[Virtual_timer,'Total_Funding'] = Virtual_total_funding
            History_KLine_Export.loc[Virtual_timer,'Trade_Number'] = order_quantity
            History_KLine_Export.loc[Virtual_timer,'Trade_Margin'] = margin
            History_KLine_Export.loc[Virtual_timer,'Taker_fee'] = temp_fee
            return 0
        Virtual_total_funding = Virtual_total_funding - temp_fee - margin
        History_KLine_Export.loc[Virtual_timer,'Total_Funding'] = Virtual_total_funding
        History_KLine_Export.loc[Virtual_timer,'Taker_fee'] = temp_fee
        print("價格=",int(float(History_KLine.loc[Virtual_timer,'Close'])))
        print("方向 = ",order_side)
        print("Virtual_total_funding =",Virtual_total_funding,"; 數量=",order_quantity,"; 開倉手續費=",temp_fee,"; 保證金 = ",margin)
        Virtual_position_display(order_quantity,margin,order_side)
        return 123
        
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
def get_order(order_symbol:str, order_orderid:int) -> float:
    """_summary_
    透過幣種與訂單編號,來查詢訂單資訊-平均價格
    Args:
        order_symbol (str): 幣種
        order_orderid (int): 訂單編號

    Returns:
        float: 如果有找到訂單,則回傳訂單資訊-平均價格;如果沒有則回傳 0
    """
    global Virtual_timer
    global Virtual_flag
    global Virtual_position_open_price
    global Virtual_position_falg
    if Virtual_flag:
        if Virtual_position_falg:
            return Virtual_position_open_price
        else:
            return 0
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

def Virtual_position_display(trade_num:float=0.0, money:float=0.0,flow:str='') -> str:
    """_summary_
    用來記錄現在有沒有倉位
    Args:
        trade_num (float): 開倉時的數量
        money (float): 開倉時保證金
        flow (str): 放向,ex:BUY

    Returns:
        str: 結果
    """
    global Virtual_position_falg
    global Virtual_position
    global Virtual_position_way
    global Virtual_position_margin
    global Virtual_position_open_price
    global Virtual_position_trade_num
    global Virtual_total_funding
    global Virtual_timer
    global History_KLine_Export
    global print_message_queue
    #global #print_terminal
    
    data_message = f"Virtual_timer ={Virtual_timer};Virtual_position_falg ={Virtual_position_falg}; flow={flow}"
    #print("Virtual_timer =",Virtual_timer,";Virtual_position_falg =",Virtual_position_falg,"; flow=",flow)
    print(data_message)
    print_message_queue.put(data_message)
    if Virtual_position_falg and flow == '':
        Virtual_position = \
        (int(float(History_KLine.loc[Virtual_timer,'Close']))-Virtual_position_open_price)*Virtual_position_trade_num
        if Virtual_position_way == 'SELL':
            Virtual_position = 0 - Virtual_position
        #手續費計算
        temp_fee_cal = float(History_KLine.loc[Virtual_timer,'Close']) * Virtual_position_trade_num * 0.0005
        #保證金不夠時,強制平倉
        if (Virtual_position_margin - temp_fee_cal + Virtual_position) <= 0:
            data_message = f"當前價格 = {float(History_KLine.loc[Virtual_timer,'Close'])},\
                ;計算價格 ={float(History_KLine.loc[Virtual_timer,'Close'])} \n 強制平倉"
            #print("當前價格 = ",float(History_KLine.loc[Virtual_timer,'Close']),\
            #    ";計算價格 =",int(float(History_KLine.loc[Virtual_timer,'Close'])))
            #print("強制平倉")
            print(data_message)
            print_message_queue.put(data_message)
            History_KLine_Export.loc[Virtual_timer,'Position_Status'] = "強制平倉"
            History_KLine_Export.loc[Virtual_timer,'Trade_Profit'] = Virtual_position
            History_KLine_Export.loc[Virtual_timer,'Total_Funding'] = Virtual_total_funding
            History_KLine_Export.loc[Virtual_timer,'Buy_or_Sell'] = Virtual_position_way
            History_KLine_Export.loc[Virtual_timer,'Trade_Number'] = Virtual_position_trade_num
            History_KLine_Export.loc[Virtual_timer,'Trade_Margin'] = Virtual_position_margin
            History_KLine_Export.loc[Virtual_timer,'Taker_fee'] = temp_fee_cal
            Virtual_position_falg = False
            Virtual_position = 0.0
            Virtual_position_way = ""
            Virtual_position_margin = 0.0
            Virtual_position_open_price = 0.0
            Virtual_position_trade_num = 0.0
    elif Virtual_position_falg and flow != '':
        if flow == Virtual_position_way:
            #加倉
            Virtual_position = \
                (int(float(History_KLine.loc[Virtual_timer,'Close']))-Virtual_position_open_price)*Virtual_position_trade_num
            if Virtual_position_way == 'SELL':
                Virtual_position = 0 - Virtual_position
            Virtual_position_open_price = (float(History_KLine.loc[Virtual_timer,'Close']) * trade_num + Virtual_position_open_price*Virtual_position_trade_num)/(trade_num+Virtual_position_trade_num)
            Virtual_position_margin = Virtual_position_margin + money
            Virtual_position_trade_num = trade_num + Virtual_position_trade_num
            History_KLine_Export.loc[Virtual_timer,'Position_Status'] = "加倉"
            History_KLine_Export.loc[Virtual_timer,'Buy_or_Sell'] = Virtual_position_way
            History_KLine_Export.loc[Virtual_timer,'Trade_Number'] = Virtual_position_trade_num
            History_KLine_Export.loc[Virtual_timer,'Trade_Margin'] = Virtual_position_margin
            History_KLine_Export.loc[Virtual_timer,'Trade_Profit'] = Virtual_position
            data_message = f"\
                    狀態={History_KLine_Export.loc[Virtual_timer,'Position_Status']}\
                    ;方向={History_KLine_Export.loc[Virtual_timer,'Buy_or_Sell']}\
                    ;交易數量={History_KLine_Export.loc[Virtual_timer,'Trade_Number']}\
                    ;保證金={History_KLine_Export.loc[Virtual_timer,'Trade_Margin']}\
                    獲利={History_KLine_Export.loc[Virtual_timer,'Trade_Profit']}"
            print(data_message)
            print_message_queue.put(data_message)
        else:
            if trade_num > Virtual_position_trade_num:
                #反向
                #強制關倉
                get_temp_fee = (float(History_KLine.loc[Virtual_timer,'Close']) - Virtual_position_open_price)* Virtual_position_trade_num
                if Virtual_position_way == 'SELL':
                    get_temp_fee = 0 - get_temp_fee
                Virtual_position_open_price = float(History_KLine.loc[Virtual_timer,'Close'])
                Virtual_position_margin = Virtual_position_margin + money + get_temp_fee
                Virtual_position_way = flow
                Virtual_position_trade_num = trade_num - Virtual_position_trade_num
                History_KLine_Export.loc[Virtual_timer,'Position_Status'] = "反向加倉"
                History_KLine_Export.loc[Virtual_timer,'Buy_or_Sell'] = Virtual_position_way
                History_KLine_Export.loc[Virtual_timer,'Trade_Number'] = Virtual_position_trade_num
                History_KLine_Export.loc[Virtual_timer,'Trade_Margin'] = Virtual_position_margin
            elif trade_num < Virtual_position_trade_num:
                #減倉
                get_temp_fee = (float(History_KLine.loc[Virtual_timer,'Close']) - Virtual_position_open_price)* trade_num
                if Virtual_position_way == 'SELL':
                    get_temp_fee = 0 - get_temp_fee
                Virtual_total_funding = Virtual_total_funding + get_temp_fee
                #print("#減倉; Virtual_total_funding =",Virtual_total_funding,";get_temp_fee =",get_temp_fee)
                Virtual_position_margin = Virtual_position_margin + money
                Virtual_position_trade_num = Virtual_position_trade_num - trade_num
                History_KLine_Export.loc[Virtual_timer,'Position_Status'] = "減倉"
                History_KLine_Export.loc[Virtual_timer,'Buy_or_Sell'] = Virtual_position_way
                History_KLine_Export.loc[Virtual_timer,'Trade_Number'] = trade_num
                History_KLine_Export.loc[Virtual_timer,'Trade_Margin'] = Virtual_position_margin
                History_KLine_Export.loc[Virtual_timer,'Trade_Profit'] = (float(History_KLine.loc[Virtual_timer,'Close']) - Virtual_position_open_price)*Virtual_position_trade_num
                data_message = f"\
                    狀態={History_KLine_Export.loc[Virtual_timer,'Position_Status']}\
                    ;方向={History_KLine_Export.loc[Virtual_timer,'Buy_or_Sell']}\
                    ;交易數量={History_KLine_Export.loc[Virtual_timer,'Trade_Number']}\
                    ;保證金={History_KLine_Export.loc[Virtual_timer,'Trade_Margin']}\
                    獲利={History_KLine_Export.loc[Virtual_timer,'Trade_Profit']}"
                print(data_message)
                print_message_queue.put(data_message)
            else:
                #平倉
                get_temp_fee = (float(History_KLine.loc[Virtual_timer,'Close']) - Virtual_position_open_price)* trade_num
                if Virtual_position_way == 'SELL':
                    get_temp_fee = 0 - get_temp_fee
                Virtual_total_funding = Virtual_total_funding + get_temp_fee + Virtual_position_margin
                print("#平倉; Virtual_total_funding =",Virtual_total_funding,"; get_temp_fee =",get_temp_fee,"; Virtual_position_margin=",Virtual_position_margin)
                History_KLine_Export.loc[Virtual_timer,'Position_Status'] = "平倉"
                History_KLine_Export.loc[Virtual_timer,'Buy_or_Sell'] = Virtual_position_way
                History_KLine_Export.loc[Virtual_timer,'Trade_Number'] = trade_num
                History_KLine_Export.loc[Virtual_timer,'Trade_Margin'] = Virtual_position_margin
                History_KLine_Export.loc[Virtual_timer,'Trade_Profit'] = get_temp_fee
                Virtual_position_falg = False
                Virtual_position = 0.0
                Virtual_position_way = ""
                Virtual_position_margin = 0.0
                Virtual_position_open_price = 0.0
                Virtual_position_trade_num = 0.0
                data_message = f"\
                    狀態={History_KLine_Export.loc[Virtual_timer,'Position_Status']}\
                    ;方向={History_KLine_Export.loc[Virtual_timer,'Buy_or_Sell']}\
                    ;交易數量={History_KLine_Export.loc[Virtual_timer,'Trade_Number']}\
                    ;保證金={History_KLine_Export.loc[Virtual_timer,'Trade_Margin']}\
                    獲利={History_KLine_Export.loc[Virtual_timer,'Trade_Profit']}"
                print(data_message)
                print_message_queue.put(data_message)
    elif flow != '':
        Virtual_position_open_price = float(History_KLine.loc[Virtual_timer,'Close'])
        Virtual_position = 0.0
        Virtual_position_way = flow
        Virtual_position_margin = money
        Virtual_position_trade_num = trade_num
        Virtual_position_falg = True
        History_KLine_Export.loc[Virtual_timer,'Position_Status'] = "開倉"
        History_KLine_Export.loc[Virtual_timer,'Buy_or_Sell'] = Virtual_position_way
        History_KLine_Export.loc[Virtual_timer,'Trade_Number'] = Virtual_position_trade_num
        History_KLine_Export.loc[Virtual_timer,'Trade_Margin'] = Virtual_position_margin
        History_KLine_Export.loc[Virtual_timer,'Trade_Profit'] = Virtual_position
        data_message = f"\
            狀態={History_KLine_Export.loc[Virtual_timer,'Position_Status']}\
            ;方向={History_KLine_Export.loc[Virtual_timer,'Buy_or_Sell']}\
            ;交易數量={History_KLine_Export.loc[Virtual_timer,'Trade_Number']}\
            ;保證金={History_KLine_Export.loc[Virtual_timer,'Trade_Margin']}\
            獲利={History_KLine_Export.loc[Virtual_timer,'Trade_Profit']}"
        print(data_message)
        print_message_queue.put(data_message)        
        
        

class Auto_virtual_position_cal(threading.Thread):
    """_summary_
    更新倉位
    Args:
        threading (_type_): 宣告種類
    """
    def __init__(self):
        """_summary_
        宣告後立即會執行的東西
        Args:
            queue (Queue): 都進來的存列
            total_num (int): 總資料筆數
        """
        threading.Thread.__init__(self)
        #self.queue = queue
        #self.total_num = total_num

    def run(self):
        global Virtual_timer
        global Virtual_position_falg
        old_timer = Virtual_timer
        count = 1
        
        while True:
            if Virtual_timer != old_timer:
                old_timer = Virtual_timer
                print("count =",count)
                count = count + 1
                if Virtual_position_falg:
                    Virtual_position_display()
    

def main_function(progress_bar_or_message:Queue)-> None:
    """_summary_
    用來讓另外一個程式來執行
    """
    global Virtual_position_falg
    global Virtual_position
    global Virtual_position_way
    global Virtual_position_margin
    global Virtual_position_open_price
    global Virtual_position_trade_num
    global Virtual_total_funding
    global Virtual_timer
    global History_KLine_Export
    global History_KLine
    global Start_time_str
    global End_time_str
    global Force_stop_flag
    global print_message_queue
    
    print_message_queue = progress_bar_or_message
        #=========================================================================================================================
    #啟動回測模擬
    if Virtual_flag:
        progress_bar_or_message.put_nowait(0)
        SET_START_TIME = cal_timestrip(Start_time_str+".0")
        print("SET_START_TIME=",datetime.fromtimestamp(float(SET_START_TIME/1000)))
        #print_terminal.put(f"SET_START_TIME={datetime.fromtimestamp(float(SET_START_TIME/1000))}")
        #FINISH_TIME = cal_timestrip(str(datetime.now()))
        FINISH_TIME = cal_timestrip(End_time_str+".0")
        print("FINISH_TIME=",datetime.fromtimestamp(float(FINISH_TIME/1000)))
        #print_terminal.put(f"FINISH_TIME={datetime.fromtimestamp(float(FINISH_TIME/1000))}")
        print(datetime.fromtimestamp(float(SET_START_TIME/1000)),"到",datetime.fromtimestamp(float(FINISH_TIME/1000)),"回測資料")
        History_KLine = pd.DataFrame(get_history_kline(interval=Virtual_interval,START_TIME=SET_START_TIME, finish_end_time=FINISH_TIME),columns=Kline_column)
        if len(History_KLine.index) < 50:
            return_message = "當前資料筆為"+str(len(History_KLine.index))+"小於最小回測資料筆數50筆,終止回測"
            return return_message
        print(History_KLine)
        #匯出資料
        #History_KLine.to_csv("History_KLine.csv")
        #複製資料
        History_KLine_Export = History_KLine.copy()
        #將時間轉換為人可讀的日期
        History_KLine_Export['Open_time'] = pd.to_datetime(History_KLine_Export['Open_time'], unit='ms')
        History_KLine_Export['Close_time'] = pd.to_datetime(History_KLine_Export['Close_time'], unit='ms')
        #print("get_kline =",get_kline())
        #print("History_KLine = ",History_KLine.values.tolist())
        #增加欄位
        History_KLine_Export['Position_Status'] = ''
        History_KLine_Export['Trade_Profit'] = ''
        History_KLine_Export['Buy_or_Sell'] = ''
        History_KLine_Export['Total_Funding'] = ''
        History_KLine_Export['Trade_Number'] = ''
        History_KLine_Export['Trade_Margin'] = ''
        History_KLine_Export['Taker_fee'] = ''
    #=========================================================================================================================
    print("wallet =",get_balance('USDT'))
    #print_terminal.put(f"wallet ={get_balance('USDT')}")
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
    if Virtual_flag:
        start_finance = Virtual_total_funding
        data_message = f"虛擬初始資金 = {Virtual_total_funding}"
        print(data_message)
        #print_terminal.put(data_message)
    else:
        data_message = f"初始資金 ={start_finance}"
        print(data_message)
        progress_bar_or_message.put(data_message)
    
    #倉位管理以100為單位,每100下0.01張(要購買幣種的數量)
    trade_num = int(start_finance/100)*0.01
    data_message = f"倉位管理={trade_num}"
    print(data_message)
    progress_bar_or_message.put(data_message)
    
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
        if Virtual_flag or Force_stop_flag:
            break
        new_time = time.time()
        if int(new_time) % 60 == 0:
            old_time = new_time - 60
            data_message = f"old_time={old_time}; new_time={new_time}"
            #print("old_time=",old_time,"; new_time=",new_time)
            print(data_message)
            progress_bar_or_message.put(data_message)
            break
    while True:
        if Virtual_flag:
            trade_flag = Virtual_position_falg
        if not trade_flag:
            new_time = time.time()
            if Virtual_flag or new_time - old_time >= 60:
                #判斷當前方向
                print("===========================================================")
                progress_bar_or_message.put("===========================================================")
                if not Virtual_flag:
                    data_message = f"start_time = {datetime.now()}"
                    #print('start_time = {}'.format(datetime.now()))
                    print(data_message)
                    progress_bar_or_message.put(data_message)
                    open_time_direction, kline_data = indicator_cal()
                    data_message = f"end_time = {datetime.now()}"
                    #print('end_time = {}'.format(datetime.now()))
                    #print(datetime.now())
                    print(data_message)
                    progress_bar_or_message.put(data_message)
                else:
                    data_message = f"History date = {History_KLine_Export.loc[Virtual_timer,'Open_time']}"
                    #print("History date =",History_KLine_Export.loc[Virtual_timer,'Open_time'])
                    print(data_message)
                    #print_terminal.put(data_message)
                    open_time_direction, kline_data = indicator_cal()
                if open_time_direction != '':
                    if Virtual_flag:
                        open_time = pd.to_datetime(History_KLine.loc[Virtual_timer,'Open_time'],unit='ms')
                    else:
                        open_time = datetime.now()
                    start_finance = float(get_balance('USDT'))
                    trade_num = int(start_finance/100)*0.01
                    logging.debug(f"開單 =>start_finance={start_finance}; trade_num={trade_num}")
                    order_id = new_order(SYMBOL, open_time_direction, trade_num)
                    #錯誤發生時,order_id = 0
                    if order_id != 0:
                        open_price = get_order(SYMBOL, order_id)
                        trade_flag = True
                        open_fee = open_price / 20 *trade_num * 0.0004
                        data_message = f"開單日期{open_time}, 開單價格{open_price},開單方向{open_time_direction},開單數量{trade_num}, 開單手續費{open_fee}"
                        
                        #print('開單日期{}, 開單價格{}, 開單數量{}, 開單手續費{}'.format(
                        #    open_time, open_price, trade_num, open_fee))
                        print(data_message)
                        progress_bar_or_message.put(data_message)
                    else:
                        temp_fee = int(float(History_KLine.loc[Virtual_timer,'Close']))*trade_num*0.005
                        margin = int(float(History_KLine.loc[Virtual_timer,'Close']))*trade_num/20
                        data_message = f"當前資金={Virtual_total_funding}; temp_fee={temp_fee}; margin={margin}低於建倉價格"
                        #print("當前資金=",Virtual_total_funding,"; temp_fee=",temp_fee, "; margin=",margin,"低於建倉價格") 
                        data_message = data_message + "\n" + "訂單失敗,跳過此次開單"
                        #print("訂單失敗,跳過此次開單")
                        print(data_message)
                        progress_bar_or_message.put(data_message)
                old_time = new_time
                if not Virtual_flag:
                    for i in range(59):
                        print(f"倒數{60-i}秒")
                        time.sleep(1)
                        if Force_stop_flag:
                            break
                    
        elif trade_flag:
            new_time = time.time()
            if Virtual_flag or new_time - old_time >= 60:
                #方向為BUY時
                now_price = get_price(SYMBOL)
                new_time = time.time()
                if Virtual_flag or new_time - old_time >= 60:
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
                            if Virtual_flag and Virtual_position_falg:
                                Virtual_position_falg =False
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
                                if Virtual_flag and Virtual_position_falg:
                                    Virtual_position_falg =False
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
                            if Virtual_flag and Virtual_position_falg:
                                Virtual_position_falg =False
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
                                if Virtual_flag and Virtual_position_falg:
                                    Virtual_position_falg =False
                                dup_time = 0
                                open_time_direction = ''
                                open_time = ''
                                open_price = 0.0
                                start_finance = float(get_balance('USDT'))
                                trade_num = int(start_finance / 100) * 0.01
                                trade_flag = False
                            else:
                                dup_profit += 1
        if Virtual_flag and Virtual_position_falg:
            Virtual_position_display()
            print("open_time_direction=",open_time_direction,"; now_price=",get_price(SYMBOL),"; open_price = ",open_price, "; dup_profit=",dup_profit)
            print("當前價格=",History_KLine.loc[Virtual_timer,'Close'])
            print("#已有倉位; Virtual_position =",Virtual_position,"; Virtual_position_open_price=",Virtual_position_open_price, \
                "; Virtual_position_margin =",Virtual_position_margin, "; Virtual_position_trade_num =",Virtual_position_trade_num,\
                    "; Virtual_position_way=",Virtual_position_way)
        Virtual_timer = Virtual_timer + 1
        start_finance = Virtual_total_funding
        if Virtual_flag and int(Virtual_timer/len(History_KLine.index)*100) != int(Virtual_timer-1/len(History_KLine.index)*100):
            progress_bar_or_message.put_nowait(int(Virtual_timer/len(History_KLine.index)*100))
        if Virtual_flag and Virtual_timer >= len(History_KLine.index):
            progress_bar_or_message.join()
            #print_terminal.join()
            print("Virtual_total_funding = ",Virtual_total_funding)
            Start_datetime = History_KLine_Export.loc[0,'Open_time'].to_pydatetime().strftime(format='%Y-%m-%d_%H-%M')
            End_datetime = History_KLine_Export.loc[len(History_KLine_Export.index)-1,'Open_time'].to_pydatetime().strftime(format='%Y-%m-%d_%H-%M')
            History_KLine_Export.to_csv(f"{SYMBOL}_{Virtual_interval}_{Start_datetime}_to_{End_datetime}.csv")
            Virtual_timer = 0
            print("回測結束")
            return_message = "回測結束"+"\nVirtual_total_funding = "+str(Virtual_total_funding)+\
                "\n已匯出資料=>"+ f"{SYMBOL}_{Virtual_interval}_{Start_datetime}_to_{End_datetime}.csv"
            return return_message
            break
        if Force_stop_flag:
            break       
    if Virtual_flag and Virtual_timer >= len(History_KLine.index):
        return_message = "回測結束"+"\nVirtual_total_funding = "+str(Virtual_total_funding)+\
                "\n已匯出資料=>"+ f"{SYMBOL}_{Virtual_interval}_{Start_datetime}_to_{End_datetime}.csv"
        return return_message
    if Force_stop_flag:
        Force_stop_flag = False
        return "強制終止"




if __name__ == "__main__": 
   pass

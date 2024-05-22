'''
測試csv寫入
'''
import time
from datetime import datetime
import sys
import os
import configparser
import csv
import shutil
import pandas as pd
from pandas.core.frame import DataFrame


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






if __name__ == "__main__":
    with open('test_csv.csv','w',newline='',encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file, dialect='excel')
        csv_writer.writerow(Kline_column)
        csv_writer.writerow(['1','2','3','4','5','6','7','8','9','10','11','12'])
        csv_writer.writerow(['13','14'])
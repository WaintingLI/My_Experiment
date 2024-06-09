'''
用來存檔ini檔案
'''
import sys
import os




#切換命令提示字元到Python檔案所在的目錄
#檢查當前工作路徑是否在Python檔案的所在地,如果是就不會切換目錄
if os.path.dirname(sys.argv[0]):
    os.chdir(os.path.dirname(sys.argv[0]))



#讀取檔案參數與全域變數
#cf=configparser.ConfigParser()
#cf.read_file(open('config.ini', 'r', encoding='UTF-8'))
#JIRASOFWARE_IP = cf.get("APP_Info","JiraSoftware_ip")
#ADMIN_USERNAME = cf.get("APP_Info","Admin_Username")
#ADMIN_PASSWORD = cf.get("APP_Info","Admin_Password")
#ADMIN_EMAIL = cf.get("APP_Info","Admin_E-Mail")
#獲取專案的名稱與設定
#PROJECT_NAME = cf.get("Project","Project_Name")
#PROJECT_KEY = cf.get("Project","Project_Key")


def save_ini(file_path: str, section: str, option: str, value: str) -> bool:
    """_summary_
    用來存檔ini,且不移除註解,僅修改相對應的option值,每一次只能修改一個選項
    ※如果沒有對應的section或option,將不會修改ini檔案
    Args:
        file_path (str): 要修改的ini檔案路徑
        section (str): ini檔案中的section(ex:[APP_Info])
        option (str): ini檔案中的option(ex:Admin_Username)
        value (str): option要修改的值

    Returns:
        bool: 修改成功回傳True;否則回傳False
    """
    old_datas = list()
    new_datas = list()
    #用來判斷是否有找到[Section]相同的字串
    section_find_flag = False
    #用來判斷是否有找到Option相同的字串
    option_find_flag = False

    if not os.path.isfile(file_path):
        print(file_path,"is not found")
        return
    #讀取檔案
    with open(file_path,"r",encoding="utf-8") as f:
        meta_datas = f.readlines()
        for item in meta_datas:
            old_datas.append(item)
    #處理字串,並且依section(ex:[APP_Info])與option(ex:Admin_Username =)來寫入對應的資料
    for index,item in enumerate(old_datas):
        #移除當前字串的所有空格,方便檢查
        string_meta = item.replace(" ","")
        #檢查當前字串是否為註解,是的話,跳過
        if string_meta[0] == "#":
            new_datas.append(old_datas[index])
            continue
        #找尋相對應的Section
        if string_meta[0] == "[" and not section_find_flag:
            if string_meta[0:len(section)] == section:
                section_find_flag =True
        else:
            if not section_find_flag:
                new_datas.append(old_datas[index])
                continue
        #找到Section後,在找到相對應的option
        string_meta_2_option = string_meta[0:string_meta.find("=")]
        if string_meta_2_option == option:
            string_index = old_datas[index].find("=")
            add_string = old_datas[index][0:string_index] + "= " +value+"\n"
            new_datas.append(add_string)
            option_find_flag = True
        else:
            new_datas.append(old_datas[index])

    if section_find_flag and option_find_flag:
        #創造或複蓋文件
        with open(file_path,"w",encoding="utf-8") as f:
            f.writelines(new_datas)
        return True
    else:
        if section_find_flag:
            print("在Section下,找不到相同的Option值")
        elif option_find_flag:
            print("找不到相同的Section值")
        else:
            print("找不到Section與Option值")
        print("將不會修改檔案")
        return False

if __name__ == "__main__":
    # 要檢查的檔案路徑
    #filepath = "/etc/motd"
    #FILEPATH = "config-test.ini"

    # 檢查檔案是否存在

    #if os.path.isfile(FILEPATH):
    #    print("檔案存在。")
    #else:
    #    print("檔案不存在。")
    #字串轉16進位方法
    #print("test",string_meta[0:len(section)].encode('utf-8').hex())
    save_ini("config.ini",
             "[Binance_Setting]",
             "API_KEY",
             "456")

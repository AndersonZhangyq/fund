# 导入需要的模块
import requests
from bs4 import BeautifulSoup
import re
import numpy as np
import pandas as pd
import json
from datetime import datetime, timedelta

# import matplotlib
# #指定默认字体
# matplotlib.rcParams['font.sans-serif'] = ['SimHei']
# matplotlib.rcParams['font.family']='sans-serif'
# #解决负号'-'显示为方块的问题
# matplotlib.rcParams['axes.unicode_minus'] = False

# 抓取网页
def get_url(url, params=None, proxies=None):
    rsp = requests.get(url, params=params, proxies=proxies)
    rsp.raise_for_status()
    return rsp.text


# 从网页抓取数据
def get_fund_data(code, per=10, sdate="", edate="", proxies=None):
    url = "http://fund.eastmoney.com/f10/F10DataApi.aspx"
    params = {
        "type": "lsjz",
        "code": code,
        "page": 1,
        "per": per,
        "sdate": sdate,
        "edate": edate,
    }
    html = get_url(url, params, proxies)
    soup = BeautifulSoup(html, "html.parser")

    # 获取总页数
    pattern = re.compile(r"pages:(.*),")
    result = re.search(pattern, html).group(1)
    pages = int(result)

    # 获取表头
    heads = []
    for head in soup.findAll("th"):
        heads.append(head.contents[0])

    # 数据存取列表
    records = []

    # 从第1页开始抓取所有页面数据
    page = 1
    while page <= pages:
        params = {
            "type": "lsjz",
            "code": code,
            "page": page,
            "per": per,
            "sdate": sdate,
            "edate": edate,
        }
        html = get_url(url, params, proxies)
        soup = BeautifulSoup(html, "html.parser")

        # 获取数据
        for row in soup.findAll("tbody")[0].findAll("tr"):
            row_records = []
            for record in row.findAll("td"):
                val = record.contents

                # 处理空值
                if val == []:
                    row_records.append(np.nan)
                else:
                    row_records.append(val[0])

            # 记录数据
            records.append(row_records)

        # 下一页
        page = page + 1

    # 数据整理到dataframe
    np_records = np.array(records)
    data = pd.DataFrame()
    for col, col_name in enumerate(heads):
        data[col_name] = np_records[:, col]

    return data


# 主程序
if __name__ == "__main__":
    code_list = ["003516", "001510", "002621", "161219", "001500"]
    data = {}
    for code in code_list:
        ret = get_fund_data(
            code, per=49, sdate="2019-01-01", edate=datetime.now().strftime("%Y-%m-%d")
        )
        # 修改数据类型
        # ret["净值日期"] = pd.to_datetime(ret["净值日期"], format="%Y/%m/%d")
        ret["日增长率"] = ret["日增长率"].str.strip("%").astype(float)
        ret = ret[["净值日期", "日增长率"]]
        # 按照日期升序排序并重建索引
        ret = ret.sort_values(by="净值日期", axis=0, ascending=True).reset_index(drop=True)
        ret = ret.dropna()
        data[code] = ret.values.tolist()
        # data[code] = {k: v for k, v in ret.values.tolist()}
    # print(data)
    json.dump(data, open("data.json", "w+"))

    # 上证指数
    request = requests.get(
        f'http://quotes.money.163.com/service/chddata.html?code=1399300&start=20190101&end={datetime.now().strftime("%Y%m%d")}&fields=PCHG'
    )
    data = request.text.split("\r\n")
    data.pop(0)
    data = {l.split(",")[0]: float(l.split(",")[-1]) for l in data if len(l) > 0}
    with open("399300.json", "w+") as f:
        json.dump(data, f)

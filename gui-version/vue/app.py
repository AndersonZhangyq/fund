import json
import os
import re
from datetime import datetime
from multiprocessing import Pool, freeze_support
import sys
import platform
import numpy as np
import pandas as pd
import requests
from selectolax.parser import HTMLParser
import eel


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
    html_parser = HTMLParser(html)

    # 获取总页数
    pattern = re.compile(r"pages:(.*),")
    result = re.search(pattern, html).group(1)
    pages = int(result)

    # 获取表头
    heads = []
    for head in html_parser.tags("th"):
        heads.append(head.text())

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
        html_parser = HTMLParser(html)

        # 获取数据
        for row in html_parser.css("tbody > tr"):
            row_records = []
            for record in row.css("td"):
                val = record.text()

                # 处理空值
                if len(val) == 0:
                    row_records.append(np.nan)
                else:
                    row_records.append(val)

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


class Generator:
    def __init__(self, num_funds, target_sum=10):
        self.num_funds = num_funds
        self.target_sum = target_sum

    def generate(self):
        self.result = []
        self._generate(self.num_funds, left=self.target_sum, pre_comb=[])
        return self.result

    def _generate(self, num_funds, left, pre_comb=[]):
        if num_funds == 1:
            if len(self.result) % 500 == 0:
                print(len(self.result))
            self.result.append(pre_comb + [left])
        else:
            for i in range(0, left + 1):
                self._generate(num_funds - 1, left - i, pre_comb + [i])


def process_tuple_number_format(input_data):
    input_data = list(input_data)
    tmp = ",".join(map(lambda x: "{0:.2%}".format(x), input_data[0]))
    input_data[0] = tmp
    return ",".join(map(str, input_data))


def update_data(code_list):
    fund_data = {}
    # 获取自 2019-01-01 的数据
    # 组合
    for code in code_list:
        ret = get_fund_data(
            code,
            per=49,
            sdate="2019-01-01",
            edate=datetime.now().strftime("%Y-%m-%d"),
        )

        ret["日增长率"] = ret["日增长率"].str.strip("%").astype(float)
        ret = ret[["净值日期", "日增长率"]]
        # 按照日期升序排序并重建索引
        ret = ret.sort_values(by="净值日期", axis=0, ascending=True).reset_index(
            drop=True
        )
        ret = ret.dropna()

        fund_data[code] = ret.values.tolist()

    # 上证指数
    response = requests.get(
        f'http://quotes.money.163.com/service/chddata.html?code=1399300&start=20190101&end={datetime.now().strftime("%Y%m%d")}&fields=PCHG'
    )
    hs300 = response.text.split("\r\n")
    hs300.pop(0)
    hs300 = [
        [l.split(",")[0], float(l.split(",")[-1])] for l in hs300 if len(l) > 0
    ]
    fund_data["399300"] = sorted(hs300, key=lambda x: x[0])
    return fund_data


def get_result(code_list_txt, force_update, duration):
    data_path = "data"
    os.makedirs(data_path, exist_ok=True)
    output_path = "output"
    os.makedirs(output_path, exist_ok=True)
    code_list = ["003516", "001510", "002621", "161219", "001500"]
    if code_list_txt is None or len(code_list_txt) == 0:
        print(f"未提供基金代码文件缺失，将使用默认值 {code_list}")
    else:
        code_list = [i.strip().strip("\'\"") for i in code_list_txt.split(",")]
        print(f"读取到的基金代码为 {code_list}")
    num_funds = len(code_list)
    # 枚举权重
    with Pool() as p:
        result = p.apply_async(Generator(num_funds, 10).generate)
        # possible_combinations = Generator(num_funds, 10).generate()

        today_string = datetime.now().strftime("%Y-%m-%d")
        force_update = force_update
        if not os.path.exists(today_string):
            print("未找到本地数据或已过期，重新获取")
            force_update = True
        with open(today_string, "w+") as f:
            pass
        fund_data = None
        if force_update:
            fund_data = update_data(code_list)
            json.dump(fund_data, open(f"{data_path}/fund_data.json", "w+"))
        else:
            fund_data = json.load(open(f"{data_path}/fund_data.json"))
            saved_fund_data_list = fund_data.keys()
            if all([c in saved_fund_data_list for c in code_list]):
                print("使用本地数据")
            else:
                print("本地数据的基金代码不匹配，重新获取")
                fund_data = update_data(code_list)
                json.dump(fund_data, open(f"{data_path}/fund_data.json", "w+"))

        # 计算
        last_date = sorted([data[-1][0] for data in fund_data.values()])[0]
        print(f"去掉缺省数据后的最新数据日期：{last_date}")
        series = []
        code_to_idx = {}
        # 只保留 last_date 之前的数据
        for key, value in fund_data.items():
            while value[-1][0] != last_date:
                fund_data[key].pop(-1)
            dict_value = {date: gain for date, gain in value}
            series.append(pd.Series(dict_value))
            code_to_idx[key] = len(code_to_idx)
        print(code_to_idx)
        df = pd.concat(series, axis=1)
        df.sort_index(inplace=True)
        if not df.apply(
            lambda s: pd.to_numeric(s, errors="coerce").notnull().all()
        ).all():
            print("Potenial bug: Some value is not numeric.")

        # 计算每天的实际收益率，每天的收益率累加得到
        duration = duration
        hs300_df = df[code_to_idx["399300"]].tail(duration)
        hs300_gain = hs300_df.cumsum()
        selected_df = df[
            [idx for code, idx in code_to_idx.items() if code != "399300"]
        ].tail(duration)
        selected_gain = selected_df.cumsum()

        possible_combinations = result.get()
    weight = np.array(possible_combinations) / 10
    obj = weight @ np.array(selected_gain.iloc[-1]).reshape(num_funds, 1)
    obj = obj.squeeze()
    gain_per_day = weight @ np.array(selected_gain).reshape(num_funds, -1)
    constraint = gain_per_day - np.array(hs300_gain)
    percent_of_statisfy = (constraint > 0).sum(axis=-1) / duration

    # 保存结果
    origin_result = [
        (tuple(comb), round(percent_of_statisfy[idx], 2), round(obj[idx], 2))
        for idx, comb in enumerate(weight.tolist())
    ]
    with open(f"{output_path}/result-{duration}.json", "w+") as f:
        json.dump(origin_result, f)
    # to csv
    csv_header_code = [0 for _ in range(num_funds)]
    for code, idx in code_to_idx.items():
        if idx < num_funds:
            csv_header_code[idx] = code
    csv_header = csv_header_code + ["约束符合率", "收益率"]
    origin_result_csv_format = [",".join(csv_header)]
    origin_result_csv_format += [process_tuple_number_format(v) for v in origin_result]
    with open(f"{output_path}/result-{duration}.csv", "w+", encoding="GBK") as f:
        f.write("\n".join(origin_result_csv_format))

    # 简单分析
    simple_analysis = {v[0]: [] for v in origin_result}
    for idx, v in enumerate(sorted(origin_result, key=lambda x: x[1], reverse=True)):
        simple_analysis[v[0]].append(idx)
    for idx, v in enumerate(sorted(origin_result, key=lambda x: x[2], reverse=True)):
        simple_analysis[v[0]].append(idx)
    simple_analysis = sorted(simple_analysis.items(), key=lambda x: x[1][-1] + x[1][-2])
    simple_analysis = [[v[0], v[1][0], v[1][1]] for v in simple_analysis]
    with open(f"{output_path}/analysis-{duration}.txt", "w+", encoding="GBK") as f:
        f.write("\n".join(map(str, simple_analysis)))

    csv_header = csv_header_code + ["约束符合率排名", "收益率排名"]
    csv_format = [",".join(csv_header)]
    csv_format += [process_tuple_number_format(v) for v in simple_analysis]
    with open(f"{output_path}/analysis-{duration}.csv", "w+") as f:
        f.write("\n".join(csv_format))

    print(f"before filter: {len(simple_analysis)}")
    simple_analysis_filtered = list(
        filter(lambda x: x[-1] < 200 and x[-2] < 200, simple_analysis)
    )
    print(f"after filter: {len(simple_analysis_filtered)}")
    for l in map(str, simple_analysis_filtered):
        print(l)
    print(csv_header)
    return origin_result_csv_format


@eel.expose
def process(code_list_txt=None, force_update=False, duration=30):
    duration = int(duration)
    origin_result_csv_format = get_result(code_list_txt, force_update, duration)
    header = origin_result_csv_format[0].split(",")
    origin_dataset = origin_result_csv_format[1:]
    dataset = []
    for d in origin_dataset:
        d = d.split(",")
        cur_item = {}
        for idx, h in enumerate(header):
            cur_item[h] = d[idx]
        dataset.append(cur_item)
    return {"header": header, "dataset": dataset}


@eel.expose  # Expose function to JavaScript
def say_hello_py(x):
    """Print message from JavaScript on app initialization, then call a JS function."""
    print("Hello from %s" % x)
    eel.say_hello_js("Python {from within say_hello_py()}!")


def start_eel(develop):
    """Start Eel with either production or development configuration."""
    if develop:
        directory = 'src'
        app = None
        page = {'port': 3000}
    else:
        directory = 'web'
        app = 'chrome-app'
        page = 'index.html'

    eel.init(directory)
    say_hello_py("Python World!")
    eel.say_hello_js(
        "Python World!"
    )  # Call a JavaScript function (must be after `eel.init()`)

    eel_kwargs = dict(
        host="localhost",
        port=9000,
        # size=(1280, 800),
    )
    try:
        eel.start(**eel_kwargs)

    except EnvironmentError:
        # If Chrome isn't found, fallback to Microsoft Edge on Win10 or greater
        if sys.platform in ["win32", "win64"] and int(platform.release()) >= 10:
            eel.start(page, mode="edge", **eel_kwargs)
        else:
            raise


if __name__ == "__main__":
    freeze_support()
    print("Opening python...")
    start_eel(False)

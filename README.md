# 股票 / ETF 量化分析系统 V1

面向 A 股和场内 ETF 的日线辅助分析工具。它会计算均线、RSI、MACD、
成交量、动量和 ATR，输出综合评分、交易观察区间与基础历史回测。

> 本项目只用于研究和辅助决策，不保证收益，也不构成投资建议。

## 安装

建议使用 Python 3.11：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 命令行运行

联网获取并分析沪深 300 ETF：

```powershell
python main.py 510300 --refresh --backtest
```

首次联网成功后，行情会缓存在 `data/510300.csv`。后续不加
`--refresh` 即可离线运行。

使用自己的 CSV：

```powershell
python main.py 510300 --csv .\your_data.csv --backtest
```

CSV 支持中文字段 `日期,开盘,最高,最低,收盘,成交量`，也支持英文字段
`date,open,high,low,close,volume`，至少需要 121 条日线。

## 网页界面

```powershell
streamlit run app.py
```

浏览器中输入证券代码并点击“开始分析”。

## 当前策略

- 趋势：收盘价与 MA20、MA60、MA120 的关系
- 技术：RSI14、MACD
- 量价：成交量相对 20 日均量、20 日动量
- 风险：ATR14 / 当前价格
- 执行假设：回测使用前一日收盘信号、下一日开盘成交，并计入双边费率

第一版不包含估值、新闻、实时盘口和自动下单。先验证日线策略逻辑，
再决定是否加入持仓管理、全市场扫描和通知模块。


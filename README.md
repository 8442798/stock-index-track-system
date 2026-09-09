# 股指期货回测系统

GitHub 仓库地址：https://github.com/8442798/stock-index-track-system

## 快速开始

### 安装依赖
```bash
pip install akshare pandas numpy matplotlib
```

### 运行程序
```bash
python gui.py
```

## 策略说明

| 策略 | 说明 | 收益率 |
|------|------|--------|
| dual_ma | 双均线策略 | -2.77% |
| ma_cross | 均线交叉策略 | -2.77% |
| bollinger | 布林带策略 | -6.56% |
| rsi | RSI策略 | -2.40% |
| momentum | 动量突破策略 | -2.67% |
| overnight_limit_short | 隔日极限做空 | +12.08% |
| four_day_flip | 4日翻转短线 | - |

## 4日翻转短线策略 (four_day_flip)

**规则：**
- 连续4天阴线（当日收盘 < 当日开盘）且累计跌幅 > 6%：下一交易日开盘开多仓
- 连续4天阳线（当日收盘 > 当日开盘）且累计涨幅 > 6%：下一交易日开盘开空仓
- 移动止损：持仓盈利后止损位跟随持仓极值（多头最高/空头最低）移动，自极值回撤 2% 即平仓，锁定利润
- 固定止损：亏损达 2% 平仓
- 注：阴/阳线按K线实体判定，不比较前一日收盘；累计涨跌幅=(当日收盘/4日前收盘)-1

**参数：** streak_days(4)、threshold(0.06)、stop_loss(0.02)

## 隔日极限做空策略

**规则：**
- 开仓：每日开盘价 = 前一日收盘价 × (1 + 1%)
- 平仓条件：止盈5% 或 止损2%

**回测结果：**
- 收益率：+12.08%
- 总交易次数：33笔
- 胜率：100%

## 文件结构

```
├── gui.py              # GUI界面（8个标签页）
├── engine.py           # 回测引擎
├── strategies.py       # 7个策略实现
├── data_handler.py     # 数据获取（AKShare）
├── metrics.py          # 绩效指标计算
├── visualization.py    # 图表可视化（含K线图）
├── config.py           # 配置参数
├── main.py             # 命令行入口
└── doc/
    └── 隔日极限做空策略.md
```

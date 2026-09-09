# AGENTS.md

本项目工作指南，供 AI 编码代理（如 opencode）在本代码库中工作时参考。

## 项目概述

股指期货量化回测系统。支持多策略回测、绩效分析、可视化图表，提供 tkinter GUI 和命令行两种使用方式。数据源使用 AKShare（免费），主要针对中金所股指期货（IF/IH/IC/IM）。

## 常用命令

```bash
# 启动 GUI
python gui.py

# 命令行回测（查看所有可用参数）
python main.py --help

# 列出可用策略
python main.py --list-strategies

# 直接运行回测
python main.py --strategy bollinger --symbol IF0 --start 2025-09-01 --end 2026-09-01
```

**验证脚本**：修改 engine.py / strategies.py 后，建议用一次性脚本（如 `test_*.py`）调用引擎跑模拟数据验证买卖对逻辑正确，验证后删除临时脚本。

## 运行环境

- Python 3.9.9（本机 `D:\Python\Python39`）
- 依赖：pandas 2.3.3、numpy 2.0.2、matplotlib 3.9.4、akshare 1.18.88、Pillow
- 中文字体：matplotlib 需使用 SimHei/Microsoft YaHei（已在 visualization.py 配置）
- Windows 平台，PowerShell 环境（不要使用 `&&`、`head` 等 unix 语法）

## 架构与模块职责

| 文件 | 职责 | 关键类/函数 |
|------|------|------------|
| `main.py` | CLI 入口，无头回测 | `run_backtest()`, `main()` |
| `gui.py` | tkinter GUI，8 个标签页 | `BacktestGUI` |
| `engine.py` | 回测引擎核心 | `Order/Position/Trade/Portfolio/BacktestEngine/Strategy` |
| `strategies.py` | 7 个策略实现 | `get_strategy()` 工厂 + 各 Strategy 类 |
| `data_handler.py` | 多数据源 | `AKShareDataHandler/TushareDataHandler/CSVDataHandler`, `get_data_handler()` |
| `metrics.py` | 绩效指标 | `PerformanceMetrics/PerformanceAnalyzer` |
| `visualization.py` | 图表生成 | `Visualizer`, `create_interactive_kline()`, `on_kline_motion()` |
| `config.py` | 参数配置 | `BacktestConfig/StrategyConfig`, `load_config/save_config` |
| `sample_data.py` | 生成演示数据 | — |

## 关键约定与规则

### 期货合约规范
- 合约乘数：IF/IH = 300 元/点，IC/IM = 200 元/点（引擎默认 300，经参数传入）
- 保证金比例默认 12%，手续费率 0.000023，滑点 0.2 点
- 主力连续合约用 `0` 后缀（IF0/IH0），`ak.futures_main_sina()` 获取
- 合约月份规则：当月 + 下月 + 两个季月
- 每次交易固定 **1 手**（所有策略 `position_size=1`）

### Trade.action 动作字段（重要）
- 取值：`开多 / 开空 / 平多 / 平空`
- 由 `engine.py` 的 `submit_order()` 自动推断，规则：
  - 无持仓时 BUY→开多、SELL→开空
  - 有反向持仓且 `quantity >= pos.quantity` 时 BUY→平空、SELL→平多
  - **不要**依据"当时是否已有同向持仓"判断动作（会引入历史 bug）
- GUI 表格、CSV 导出、K线买卖标记、交易分析均依赖此字段

### 开平仓逻辑（避免历史 bug）
- 策略做反转（如先平空再开多）时，若在同一次 `on_bar` 连续提交两单，**必须**在本地同步更新 `current_position` 状态（第一单提交后置 0 再提交第二单），否则第二单会被引擎误判动作。
- `metrics.py` 按开平配对（side buy+sell）计算完整轮次的盈亏，不是逐笔。

### 数据列
- DataFrame 统一列：`date, open, high, low, close, volume, open_interest`
- `date` 为 datetime 类型

### 可视化
- 回测图表用 `matplotlib.use('Agg')` 静态后端（线程安全）
- K线图标签页使用 **grid 布局**：第 0 行是悬停信息标签，第 1 行是 Canvas（见 gui.py `display_interactive_kline`）。**勿在 grid 容器里混用 pack**（会触发 TclError）
- 交互式悬停回调：`_on_kline_hover` / `_on_kline_leave`，从 `self.kline_data` 读取对应 K 线
- 选中 bollinger 策略时 K 线图绘制布林带

### GUI 线程模型
- 回测在后台线程运行（`threading.Thread`），UI 更新通过 `self.root.after(0, ...)` 调度回主线程
- 禁止在后台线程直接操作 tkinter 控件

## 修改文件时的注意事项

- **不要加注释除非必要**：遵循项目现有风格（已有中文注释为业务说明，保持中文）
- 新增策略需同步修改 4 处：
  1. `strategies.py` 新增类 + `get_strategy()` 注册
  2. `config.py` `StrategyConfig` 新增参数
  3. `gui.py` 策略下拉框 `values` + `get_default_params()` + `update_strategy_desc()` 描述
  4. `main.py` `--list-strategies` 列表
- 涉及可视化/引擎行为变更时，同步更新 README.md 与相关文档
- 运行结果图表输出到 `output/`，交易记录 CSV 用 `utf-8-sig` 编码（Excel 可读）

## 测试方式

项目未配置 pytest。验证方法：
1. 用一次性脚本 + 模拟数据跑 `BacktestEngine`，检查交易动作配对（开多↔平多、开空↔平空成对出现）
2. 验证引擎行为：直接 `import engine` 后手工构造 Order/Trade 断言动作与盈亏
3. GUI 相关改动启动 `python gui.py` 目检

## Git 工作流

- 远程仓库：`https://github.com/8442798/stock-index-track-system.git`（origin/main）
- 提交信息建议中文、前缀风格：`feat:` / `fix:` / `docs:`
- 推送到 GitHub 网络偶发超时，失败重试即可
- 只在用户明确要求时才 commit / push

## 约束
- 解析过程必须使用中文
- 先分析SYSTEM_ANALYSIS.md
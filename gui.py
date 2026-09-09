"""
股指期货回测系统 - GUI界面
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import os
import sys
from datetime import datetime
from PIL import Image, ImageTk
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BacktestConfig, StrategyConfig
from data_handler import get_data_handler
from engine import BacktestEngine
from strategies import get_strategy
from metrics import PerformanceAnalyzer
from visualization import Visualizer, create_interactive_kline


class BacktestGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("股指期货回测系统")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)
        
        # 设置样式
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # 变量
        self.chart_images = {}
        self.current_charts = {}
        
        self.create_widgets()
        
    def create_widgets(self):
        # 主容器使用grid布局
        self.root.columnconfigure(0, weight=0)  # 左侧固定
        self.root.columnconfigure(1, weight=1)  # 右侧扩展
        self.root.rowconfigure(0, weight=1)
        
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
        main_frame.columnconfigure(0, weight=0)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # 左侧配置面板（固定宽度320像素）
        left_frame = ttk.LabelFrame(main_frame, text=" 回测配置 ", padding=10)
        left_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left_frame.configure(width=320)
        left_frame.pack_propagate(False)
        
        self.create_config_panel(left_frame)
        
        # 右侧输出面板（填充剩余空间）
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        
        self.create_output_panel(right_frame)
        
        # 绑定窗口大小变化事件
        self.root.bind("<Configure>", self.on_window_resize)
        
    def create_config_panel(self, parent):
        # 滚动容器
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 绑定鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        frame = scrollable_frame
        
        # === 数据配置 ===
        data_frame = ttk.LabelFrame(frame, text="数据配置", padding=8)
        data_frame.pack(fill=tk.X, pady=(0, 8))
        
        # 数据源
        ttk.Label(data_frame, text="数据源:").pack(anchor=tk.W)
        self.data_source = ttk.Combobox(data_frame, values=["akshare", "tushare", "csv"], state="readonly")
        self.data_source.set("akshare")
        self.data_source.pack(fill=tk.X, pady=(0, 5))
        
        # 合约代码
        ttk.Label(data_frame, text="合约代码:").pack(anchor=tk.W)
        self.symbol = ttk.Entry(data_frame)
        self.symbol.insert(0, "IF0")
        self.symbol.pack(fill=tk.X, pady=(0, 5))
        
        # 日期范围
        date_frame = ttk.Frame(data_frame)
        date_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(date_frame, text="开始日期:").grid(row=0, column=0, sticky=tk.W)
        self.start_date = ttk.Entry(date_frame, width=12)
        self.start_date.insert(0, "2025-09-01")
        self.start_date.grid(row=0, column=1, padx=5)
        
        ttk.Label(date_frame, text="结束日期:").grid(row=1, column=0, sticky=tk.W, pady=(5,0))
        self.end_date = ttk.Entry(date_frame, width=12)
        self.end_date.insert(0, "2026-09-01")
        self.end_date.grid(row=1, column=1, padx=5, pady=(5,0))
        
        # === 资金配置 ===
        capital_frame = ttk.LabelFrame(frame, text="资金配置", padding=8)
        capital_frame.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Label(capital_frame, text="初始资金:").pack(anchor=tk.W)
        self.initial_capital = ttk.Entry(capital_frame)
        self.initial_capital.insert(0, "1000000")
        self.initial_capital.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(capital_frame, text="保证金比例:").pack(anchor=tk.W)
        self.margin_ratio = ttk.Entry(capital_frame)
        self.margin_ratio.insert(0, "0.12")
        self.margin_ratio.pack(fill=tk.X, pady=(0, 5))
        
        cost_frame = ttk.Frame(capital_frame)
        cost_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(cost_frame, text="手续费率:").grid(row=0, column=0, sticky=tk.W)
        self.commission_rate = ttk.Entry(cost_frame, width=10)
        self.commission_rate.insert(0, "0.000023")
        self.commission_rate.grid(row=0, column=1, padx=5)
        
        ttk.Label(cost_frame, text="滑点:").grid(row=1, column=0, sticky=tk.W, pady=(5,0))
        self.slippage = ttk.Entry(cost_frame, width=10)
        self.slippage.insert(0, "0.2")
        self.slippage.grid(row=1, column=1, padx=5, pady=(5,0))
        
        # === 策略配置 ===
        strategy_frame = ttk.LabelFrame(frame, text="策略配置", padding=8)
        strategy_frame.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Label(strategy_frame, text="选择策略:").pack(anchor=tk.W)
        self.strategy_name = ttk.Combobox(
            strategy_frame, 
            values=["dual_ma", "ma_cross", "bollinger", "rsi", "momentum", "overnight_limit_short"],
            state="readonly"
        )
        self.strategy_name.set("bollinger")
        self.strategy_name.pack(fill=tk.X, pady=(0, 5))
        self.strategy_name.bind("<<ComboboxSelected>>", self.on_strategy_change)
        
        # 策略参数区域
        self.params_frame = ttk.LabelFrame(strategy_frame, text="策略参数", padding=8)
        self.params_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.param_entries = {}
        self.create_strategy_params("bollinger")
        
        # 策略说明
        self.strategy_desc = tk.Text(strategy_frame, height=4, width=35, wrap=tk.WORD, font=("Arial", 9))
        self.strategy_desc.pack(fill=tk.X, pady=(0, 5))
        self.update_strategy_desc("bollinger")
        
        # === 按钮 ===
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.run_btn = ttk.Button(btn_frame, text="开始回测", command=self.run_backtest)
        self.run_btn.pack(fill=tk.X, pady=(0, 5))
        
        self.save_btn = ttk.Button(btn_frame, text="保存配置", command=self.save_config)
        self.save_btn.pack(fill=tk.X, pady=(0, 5))
        
        self.load_btn = ttk.Button(btn_frame, text="加载配置", command=self.load_config)
        self.load_btn.pack(fill=tk.X)
        
        # 进度条
        self.progress = ttk.Progressbar(frame, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(8, 0))
        
        self.status_label = ttk.Label(frame, text="就绪", foreground="gray")
        self.status_label.pack(anchor=tk.W, pady=(5, 0))
        
    def create_output_panel(self, parent):
        # 使用Notebook实现标签页
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 标签页1: 绩效概览
        overview_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(overview_frame, text="绩效概览")
        self.create_overview_tab(overview_frame)
        
        # 标签页2: 权益曲线
        equity_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(equity_frame, text="权益曲线")
        self.create_chart_tab(equity_frame, "equity")
        
        # 标签页3: 月度收益
        monthly_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(monthly_frame, text="月度收益")
        self.create_chart_tab(monthly_frame, "monthly")
        
        # 标签页4: 回撤分析
        drawdown_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(drawdown_frame, text="回撤分析")
        self.create_chart_tab(drawdown_frame, "drawdown")
        
        # 标签页5: 交易分析
        trade_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(trade_frame, text="交易分析")
        self.create_chart_tab(trade_frame, "trades")
        
        # 标签页6: K线图（使用grid布局）
        kline_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(kline_frame, text="K线图")
        self.kline_frame = kline_frame
        kline_frame.columnconfigure(0, weight=1)
        kline_frame.rowconfigure(1, weight=1)
        
        # 悬停信息栏（顶部，grid第0行）：固定字段名，仅数值动态变化
        self.kline_info_bar = tk.Frame(kline_frame, bg="#f0f0f0", relief=tk.SUNKEN, bd=1)
        self.kline_info_bar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        # 字段定义: (字段名, 显示宽度, 背景)
        kline_fields = [
            ("日期", 11), ("开盘", 9), ("最高", 9), ("最低", 9),
            ("收盘", 9), ("涨跌", 11), ("成交量", 11), ("振幅", 9),
        ]
        self.kline_info_labels = {}   # 字段名 -> 值Label
        for i, (name, width) in enumerate(kline_fields):
            row, col = divmod(i, 4)
            cell = tk.Frame(self.kline_info_bar, bg="#f0f0f0")
            cell.grid(row=row, column=col, sticky="w", padx=(0, 18), pady=1)
            tk.Label(cell, text=name, font=("Microsoft YaHei", 9),
                     bg="#f0f0f0", fg="#888888").pack(side=tk.LEFT)
            val = tk.Label(cell, text="--", font=("Consolas", 10),
                           bg="#f0f0f0", fg="#333333", width=width, anchor="w")
            val.pack(side=tk.LEFT)
            self.kline_info_labels[name] = val
        
        # 图表容器（grid第1行，内嵌matplotlib Figure）
        self.kline_chart_frame = tk.Frame(kline_frame, bg="white")
        self.kline_chart_frame.grid(row=1, column=0, sticky="nsew")
        self.kline_chart_frame.columnconfigure(0, weight=1)
        self.kline_chart_frame.rowconfigure(0, weight=1)
        
        self.kline_placeholder = tk.Label(self.kline_chart_frame, text="暂无图表，请先运行回测",
                                          font=("Arial", 12), foreground="gray", bg="white")
        self.kline_placeholder.grid(row=0, column=0, sticky="nsew")
        
        # 交互状态
        self.kline_data = None
        self.kline_trades = []
        self.kline_strategy_name = None
        self.kline_strategy_params = None
        self.kline_canvas = None
        self.kline_fig = None
        self.kline_vlines = {}
        self.kline_annotation = None
        self.kline_last_index = None      # 最后显示/悬停的K线索引
        self.kline_active_index = None    # 当前已绘制标记的K线索引(避免同一根内重复重绘)
        self._kline_bg = None             # blit背景缓存(整图一次，之后只重绘叠加层)
        self._kline_overlay_job = None    # 叠加层节流blit job
        self._kline_fit_size = (0, 0)
        self._kline_resize_job = None
        
        # 标签页7: 交易记录
        records_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(records_frame, text="交易记录")
        self.create_records_tab(records_frame)
        
        # 标签页7: 运行日志
        log_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(log_frame, text="运行日志")
        self.create_log_tab(log_frame)
        
    def create_overview_tab(self, parent):
        # 绩效指标展示
        metrics_frame = ttk.LabelFrame(parent, text="绩效指标", padding=15)
        metrics_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 创建指标标签
        self.metric_labels = {}
        metrics = [
            ("total_return", "总收益率", "%"),
            ("annual_return", "年化收益率", "%"),
            ("volatility", "年化波动率", "%"),
            ("max_drawdown", "最大回撤", "%"),
            ("sharpe_ratio", "夏普比率", ""),
            ("sortino_ratio", "索提诺比率", ""),
            ("calmar_ratio", "卡玛比率", ""),
            ("win_rate", "胜率", "%"),
            ("profit_factor", "盈亏比", ""),
            ("total_trades", "交易次数", ""),
            ("avg_profit", "平均盈利", "元"),
            ("avg_loss", "平均亏损", "元"),
        ]
        
        for i, (key, label, unit) in enumerate(metrics):
            row = i // 3
            col = i % 3
            
            frame = ttk.Frame(metrics_frame)
            frame.grid(row=row, column=col, padx=15, pady=8, sticky=tk.W)
            
            ttk.Label(frame, text=f"{label}:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
            lbl = ttk.Label(frame, text="--", font=("Arial", 14), foreground="#0066cc")
            lbl.pack(anchor=tk.W)
            self.metric_labels[key] = (lbl, unit)
        
        # 交易明细摘要
        summary_frame = ttk.LabelFrame(parent, text="交易摘要", padding=15)
        summary_frame.pack(fill=tk.X)
        
        self.trade_summary = tk.Text(summary_frame, height=6, width=60, font=("Consolas", 10))
        self.trade_summary.pack(fill=tk.X)
        self.trade_summary.insert(tk.END, "等待回测...")
        self.trade_summary.config(state=tk.DISABLED)
        
    def create_chart_tab(self, parent, chart_type, row=0):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(row, weight=1)
        
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        
        label = ttk.Label(frame, text="暂无图表，请先运行回测", font=("Arial", 12), foreground="gray")
        label.grid(row=0, column=0, sticky="nsew")
        
        setattr(self, f"chart_label_{chart_type}", label)
        setattr(self, f"chart_canvas_{chart_type}", None)
        setattr(self, f"chart_path_{chart_type}", None)  # 保存图表路径
        
    def create_records_tab(self, parent):
        # 工具栏
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(toolbar, text="导出CSV", command=self.export_trades).pack(side=tk.LEFT)
        self.record_count = ttk.Label(toolbar, text="共 0 条记录")
        self.record_count.pack(side=tk.RIGHT)
        
        # 交易记录表格
        columns = ("trade_id", "action", "side", "price", "quantity", "timestamp", "commission", "pnl_points", "pnl_amount", "pnl_percent")
        self.trades_tree = ttk.Treeview(parent, columns=columns, show="headings", height=20)
        
        headers = {
            "trade_id": "成交编号",
            "action": "操作",
            "side": "方向",
            "price": "成交价",
            "quantity": "数量",
            "timestamp": "时间",
            "commission": "手续费",
            "pnl_points": "股指盈亏",
            "pnl_amount": "盈亏金额",
            "pnl_percent": "盈亏比例"
        }
        
        for col, text in headers.items():
            self.trades_tree.heading(col, text=text)
            self.trades_tree.column(col, width=100, anchor=tk.CENTER)
        
        self.trades_tree.column("trade_id", width=90)
        self.trades_tree.column("timestamp", width=100)
        self.trades_tree.column("pnl_points", width=90)
        self.trades_tree.column("pnl_amount", width=110)
        self.trades_tree.column("pnl_percent", width=100)
        
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.trades_tree.yview)
        self.trades_tree.configure(yscrollcommand=scrollbar.set)
        
        self.trades_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def create_log_tab(self, parent):
        self.log_text = scrolledtext.ScrolledText(parent, font=("Consolas", 10), wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
    def create_strategy_params(self, strategy_name):
        # 清除现有参数控件
        for widget in self.params_frame.winfo_children():
            widget.destroy()
        self.param_entries.clear()
        
        # 获取策略参数
        params = self.get_default_params(strategy_name)
        
        for key, value in params.items():
            frame = ttk.Frame(self.params_frame)
            frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(frame, text=f"{key}:", width=15, anchor=tk.W).pack(side=tk.LEFT)
            entry = ttk.Entry(frame, width=10)
            entry.insert(0, str(value))
            entry.pack(side=tk.LEFT, padx=5)
            self.param_entries[key] = entry
            
    def get_default_params(self, strategy_name):
        params_map = {
            "dual_ma": StrategyConfig.DUAL_MA,
            "ma_cross": StrategyConfig.MA_CROSS,
            "bollinger": StrategyConfig.BOLLINGER,
            "rsi": StrategyConfig.RSI,
            "momentum": StrategyConfig.MOMENTUM,
            "overnight_limit_short": StrategyConfig.OVERNIGHT_LIMIT_SHORT,
        }
        return params_map.get(strategy_name, {}).copy()
    
    def update_strategy_desc(self, strategy_name):
        descs = {
            "dual_ma": "双均线策略：短期均线上穿长期均线做多，下穿做空。适合趋势行情。",
            "ma_cross": "均线交叉策略：快慢均线交叉交易，支持止盈止损。风险可控。",
            "bollinger": "布林带策略：价格触及下轨做多，触及上轨做空。适合震荡行情。",
            "rsi": "RSI策略：RSI超卖时做多，超买时做空。均值回归策略。",
            "momentum": "动量突破策略：突破N日高点做多，跌破N日低点做空。趋势跟踪。",
            "overnight_limit_short": "隔日极限做空：前收盘价+1%开空，盈利5%或亏损2%平仓。"
        }
        self.strategy_desc.config(state=tk.NORMAL)
        self.strategy_desc.delete(1.0, tk.END)
        self.strategy_desc.insert(tk.END, descs.get(strategy_name, ""))
        self.strategy_desc.config(state=tk.DISABLED)
        
    def on_strategy_change(self, event=None):
        strategy = self.strategy_name.get()
        self.create_strategy_params(strategy)
        self.update_strategy_desc(strategy)
        
    def get_config(self):
        """获取当前配置"""
        params = {}
        for key, entry in self.param_entries.items():
            val = entry.get()
            try:
                if '.' in val:
                    params[key] = float(val)
                else:
                    params[key] = int(val)
            except ValueError:
                params[key] = val
        
        return BacktestConfig(
            data_source=self.data_source.get(),
            symbol=self.symbol.get(),
            start_date=self.start_date.get(),
            end_date=self.end_date.get(),
            initial_capital=float(self.initial_capital.get()),
            margin_ratio=float(self.margin_ratio.get()),
            commission_rate=float(self.commission_rate.get()),
            slippage=float(self.slippage.get()),
            strategy_name=self.strategy_name.get(),
            strategy_params=params
        )
        
    def log(self, message):
        """写入日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def update_status(self, text):
        self.status_label.config(text=text)
        
    def update_metrics(self, metrics):
        """更新绩效指标显示"""
        updates = {
            "total_return": (metrics.total_return * 100, "%"),
            "annual_return": (metrics.annual_return * 100, "%"),
            "volatility": (metrics.volatility * 100, "%"),
            "max_drawdown": (metrics.max_drawdown * 100, "%"),
            "sharpe_ratio": (metrics.sharpe_ratio, ""),
            "sortino_ratio": (metrics.sortino_ratio, ""),
            "calmar_ratio": (metrics.calmar_ratio, ""),
            "win_rate": (metrics.win_rate * 100, "%"),
            "profit_factor": (metrics.profit_factor, ""),
            "total_trades": (metrics.total_trades, ""),
            "avg_profit": (metrics.avg_profit, "元"),
            "avg_loss": (metrics.avg_loss, "元"),
        }
        
        for key, (value, unit) in updates.items():
            if key in self.metric_labels:
                label, _ = self.metric_labels[key]
                if unit == "%":
                    label.config(text=f"{value:.2f}%")
                elif unit == "元":
                    label.config(text=f"{value:,.0f}")
                else:
                    label.config(text=f"{value:.2f}")
                    
    def update_trade_summary(self, metrics, trades):
        """更新交易摘要"""
        self.trade_summary.config(state=tk.NORMAL)
        self.trade_summary.delete(1.0, tk.END)
        
        summary = f"总交易笔数: {len(trades)}\n"
        summary += f"完整交易轮次: {metrics.winning_trades + metrics.losing_trades}\n"
        summary += f"盈利次数: {metrics.winning_trades}  |  亏损次数: {metrics.losing_trades}\n"
        summary += f"最大连胜: {metrics.max_consecutive_wins}  |  最大连亏: {metrics.max_consecutive_losses}\n"
        
        if trades:
            first_date = trades[0].timestamp.strftime('%Y-%m-%d') if hasattr(trades[0].timestamp, 'strftime') else str(trades[0].timestamp)
            last_date = trades[-1].timestamp.strftime('%Y-%m-%d') if hasattr(trades[-1].timestamp, 'strftime') else str(trades[-1].timestamp)
            summary += f"首次交易: {first_date}\n"
            summary += f"末次交易: {last_date}"
        
        self.trade_summary.insert(tk.END, summary)
        self.trade_summary.config(state=tk.DISABLED)
        
    def update_trades_table(self, trades):
        """更新交易记录表格"""
        # 清空现有数据
        for item in self.trades_tree.get_children():
            self.trades_tree.delete(item)
        
        # 配对交易计算盈亏
        contract_multiplier = 300
        open_positions = {}  # 持仓记录: symbol -> {price, side, quantity}
        
        # 插入新数据
        for trade in trades:
            timestamp = trade.timestamp.strftime('%Y-%m-%d') if hasattr(trade.timestamp, 'strftime') else str(trade.timestamp)
            side_text = "买入" if trade.side.value == "buy" else "卖出"
            
            pnl_points = ""
            pnl_amount = ""
            pnl_percent = ""
            
            symbol = trade.symbol
            
            if symbol in open_positions:
                pos = open_positions[symbol]
                
                # 判断是否为平仓操作
                is_close = (trade.side.value == 'sell' and pos['side'] == 'buy') or \
                           (trade.side.value == 'buy' and pos['side'] == 'sell')
                
                if is_close:
                    # 计算股指盈亏点数
                    if pos['side'] == 'buy':
                        points = trade.price - pos['price']
                    else:
                        points = pos['price'] - trade.price
                    
                    # 计算盈亏金额
                    pnl = points * trade.quantity * contract_multiplier - trade.commission
                    
                    # 计算盈亏比例
                    cost = pos['price'] * trade.quantity * contract_multiplier
                    if cost > 0:
                        percent = (pnl / cost) * 100
                        pnl_percent = f"{percent:.2f}%"
                    
                    pnl_points = f"{points:.2f}"
                    pnl_amount = f"{pnl:,.2f}"
                    
                    # 平仓后删除持仓记录
                    del open_positions[symbol]
                else:
                    # 加仓，更新平均价格和数量
                    total_qty = pos['quantity'] + trade.quantity
                    pos['price'] = (pos['price'] * pos['quantity'] + trade.price * trade.quantity) / total_qty
                    pos['quantity'] = total_qty
            else:
                # 开仓
                open_positions[symbol] = {
                    'price': trade.price,
                    'side': trade.side.value,
                    'quantity': trade.quantity
                }
            
            self.trades_tree.insert("", tk.END, values=(
                trade.trade_id,
                trade.action,
                side_text,
                f"{trade.price:.1f}",
                trade.quantity,
                timestamp,
                f"{trade.commission:.2f}",
                pnl_points,
                pnl_amount,
                pnl_percent
            ))
        
        self.record_count.config(text=f"共 {len(trades)} 条记录")
        
    def display_chart(self, chart_type, image_path, kline_data=None):
        """在标签页中显示图表"""
        # 保存图表路径用于窗口大小变化时重绘
        setattr(self, f"chart_path_{chart_type}", image_path)
        
        # K线图使用交互式matplotlib Figure
        if chart_type == "kline":
            if kline_data is not None:
                self.kline_data = kline_data
            self._show_kline_figure()
            return
        
        # 先获取父容器
        label = getattr(self, f"chart_label_{chart_type}", None)
        parent = label.master if label else None
        
        if label:
            label.destroy()
            
        canvas_widget = getattr(self, f"chart_canvas_{chart_type}", None)
        if canvas_widget:
            canvas_widget.destroy()
        
        if not os.path.exists(image_path) or parent is None:
            return
            
        self._draw_chart(chart_type, parent, image_path)
    
    def _show_kline_figure(self):
        """内嵌matplotlib交互式K线图：支持悬停信息、左键点击显示垂直线、窗口自适应"""
        # 清理旧figure
        if self.kline_fig is not None:
            try:
                plt.close(self.kline_fig)
            except Exception:
                pass
            self.kline_fig = None
        if self.kline_canvas is not None:
            try:
                self.kline_canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self.kline_canvas = None
        
        # 占位文本恢复
        for child in self.kline_chart_frame.winfo_children():
            child.destroy()
        self.kline_placeholder = tk.Label(self.kline_chart_frame, text="暂无图表，请先运行回测",
                                          font=("Arial", 12), foreground="gray", bg="white")
        self.kline_placeholder.grid(row=0, column=0, sticky="nsew")
        
        data = self.kline_data
        if data is None or data.empty:
            return
        
        # 创建Figure
        try:
            fig, ax1, ax2 = create_interactive_kline(
                data.copy(),
                trades=self.kline_trades or [],
                strategy_name=self.kline_strategy_name,
                strategy_params=self.kline_strategy_params
            )
        except Exception as e:
            self.log(f"K线图创建失败: {e}")
            return
        
        self.kline_fig = fig
        self.kline_axes = (ax1, ax2)
        self.kline_vlines = {}
        self.kline_annotation = None
        
        # 嵌入tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.kline_chart_frame)
        self.kline_canvas = canvas
        widget = canvas.get_tk_widget()
        widget.grid(row=0, column=0, sticky="nsew")
        
        # 事件绑定
        canvas.mpl_connect('motion_notify_event', self._on_kline_hover)
        canvas.mpl_connect('button_press_event', self._on_kline_click)
        
        self._kline_bg = None
        canvas.draw()
        # 自适应初始尺寸
        self.root.after(50, self._fit_kline_figure)
    
    def _on_kline_hover(self, event):
        """鼠标悬停K线：显示垂直线、更新数值栏；若该K线有交易则显示交易原因"""
        self._handle_kline_cursor(event)

    def _on_kline_click(self, event):
        """鼠标左键点击K线：固定当前K线的垂直线与交易原因显示"""
        if event.button != 1:
            return
        self._handle_kline_cursor(event, persist=True)
        # 点击后立即绘制最终标记，不受节流延迟
        self._flush_kline_overlay()

    def _handle_kline_cursor(self, event, persist=False):
        """处理K线光标移动/点击：更新垂直线、数值栏与交易原因注释框"""
        if self.kline_fig is None or self.kline_data is None or self.kline_data.empty:
            return
        ax = event.inaxes
        x = getattr(event, 'xdata', None)
        # 鼠标在图表区域外：保留数值栏，隐藏垂直线与注释
        if ax is None or x is None:
            if not persist and self.kline_active_index is not None:
                self.kline_active_index = None
                self._set_kline_markers_visible(False, redraw_now=True)
            return
        idx = int(round(x))
        if idx < 0 or idx >= len(self.kline_data):
            return
        
        # 更新数值栏（轻量tk更新）
        self._update_kline_info_bar(idx)
        
        # 同一根K线内移动鼠标：只刷新数值栏
        if self.kline_active_index == idx:
            return
        
        self.kline_active_index = idx
        # 立即更新artist数据（代价极小），叠加层统一节流重绘
        self._set_kline_markers(idx, x, getattr(event, 'ydata', None), ax)
        self._schedule_kline_overlay_redraw()

    def _schedule_kline_overlay_redraw(self):
        """节流合并叠加层blit：motion高频时只保留最近一次绘制"""
        if self.kline_canvas is None or self.kline_fig is None:
            return
        if self._kline_overlay_job is not None:
            return  # 已排队，等待执行（期间最新状态一并绘制）
        self._kline_overlay_job = self.root.after(40, self._flush_kline_overlay)

    def _flush_kline_overlay(self):
        """执行一次叠加层绘制并清空节流标记"""
        self._kline_overlay_job = None
        self._blit_kline_overlay()

    def _ensure_kline_markers(self):
        """惰性创建垂直线与注释artist（复用）"""
        if self.kline_fig is None or not self.kline_axes:
            return False
        if not self.kline_vlines:
            ax1, ax2 = self.kline_axes
            for ax in (ax1, ax2):
                line = ax.axvline(0, color='orange', linewidth=1.5,
                                  linestyle='--', alpha=0.9)
                line.set_visible(False)
                line.set_zorder(6)
                self.kline_vlines[ax] = line
        if self.kline_annotation is None:
            ax1, _ = self.kline_axes
            ann = ax1.annotate(
                "", xy=(0, 0), xytext=(12, -6), textcoords="offset points",
                fontsize=9, ha="left", va="top",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff9c4",
                          edgecolor="#f57f17", alpha=0.95),
                arrowprops=dict(arrowstyle="-", color="#f57f17", lw=1),
                zorder=10
            )
            ann.set_visible(False)
            self.kline_annotation = ann
        return True

    def _set_kline_markers_visible(self, visible, redraw_now=False):
        """开/关叠加层可见性；redraw_now=True立即blit，否则节流绘制"""
        changed = False
        for a, line in self.kline_vlines.items():
            if line.get_visible() != visible:
                line.set_visible(visible)
                changed = True
        if self.kline_annotation is not None and self.kline_annotation.get_visible() != visible:
            self.kline_annotation.set_visible(visible)
            changed = True
        if changed:
            if redraw_now:
                self._flush_kline_overlay()
            else:
                self._schedule_kline_overlay_redraw()

    def _set_kline_markers(self, idx, x_data, y_data, ax):
        """在指定K线处放置垂直线/注释数据并blit叠加层"""
        if not self._ensure_kline_markers():
            return
        # 垂直线
        for a, line in self.kline_vlines.items():
            try:
                line.set_xdata([idx, idx])
                line.set_visible(True)
            except Exception:
                pass
        # 注释
        day_trades = self._trades_on_kline(idx)
        ann = self.kline_annotation
        if day_trades and ann is not None:
            # 将鼠标坐标换算到价格子图坐标（注释画在价格子图上）
            ax1, ax2 = self.kline_axes
            if ax is ax2:
                px, py = ax2.transData.transform((x_data, y_data))
                x1, y1 = ax1.transData.inverted().transform((px, py))
            else:
                x1, y1 = x_data, y_data
            lines = []
            for tr in day_trades:
                lines.append(f"{tr.action} {tr.quantity}手 @ {tr.price:.2f}")
                lines.append(f"  原因: {tr.reason or '无'}")
            ann.xy = (x1, y1)
            ann.set_text("\n".join(lines))
            ann.set_visible(True)
        elif ann is not None:
            ann.set_visible(False)
        # 注：不在此处立即blit，由调用方节流调度，避免高频重绘

    def _capture_kline_bg(self):
        """完整绘制一次并缓存背景（之后叠加层blit用）"""
        try:
            self.kline_canvas.draw()
            self._kline_bg = self.kline_canvas.copy_from_bbox(self.kline_fig.bbox)
        except Exception:
            self._kline_bg = None

    def _blit_kline_overlay(self):
        """只重绘垂直线/注释叠加层（毫秒级），避免整图重绘"""
        canvas = self.kline_canvas
        if canvas is None or self.kline_fig is None:
            return
        # 画布尚未就绪或尺寸异常则退化为完整重绘
        try:
            w = canvas.get_width_height()[0]
        except Exception:
            return
        if w <= 1:
            return
        try:
            if self._kline_bg is None:
                # 首次：先临时隐藏叠加层完整绘制并缓存背景，再恢复期望可见性
                state = []
                for a, line in self.kline_vlines.items():
                    state.append((line, line.get_visible()))
                    line.set_visible(False)
                if self.kline_annotation is not None:
                    state.append((self.kline_annotation, self.kline_annotation.get_visible()))
                    self.kline_annotation.set_visible(False)
                self._capture_kline_bg()
                for artist, vis in state:
                    artist.set_visible(vis)
                if self._kline_bg is None:
                    return
            canvas.restore_region(self._kline_bg)
            for a, line in self.kline_vlines.items():
                if line.get_visible():
                    a.draw_artist(line)
            if self.kline_annotation is not None and self.kline_annotation.get_visible():
                self.kline_annotation.axes.draw_artist(self.kline_annotation)
            canvas.blit(self.kline_fig.bbox)
        except Exception:
            try:
                canvas.draw_idle()
            except Exception:
                pass

    def _set_all_markers_off(self):
        """临时隐藏所有叠加层（用于捕获干净背景）"""
        for a, line in self.kline_vlines.items():
            try:
                line.set_visible(False)
            except Exception:
                pass
        if self.kline_annotation is not None:
            try:
                self.kline_annotation.set_visible(False)
            except Exception:
                pass
    
    def _update_kline_info_bar(self, idx):
        """仅更新K线信息栏中的数值，字段名固定"""
        if self.kline_data is None or idx < 0 or idx >= len(self.kline_data):
            return
        data = self.kline_data
        labels = self.kline_info_labels
        row = data.iloc[idx]
        date_val = row['date']
        date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)
        
        open_p = row['open']
        high = row['high']
        low = row['low']
        close = row['close']
        volume = row['volume']
        
        # 涨跌额/幅（相对昨收）
        prev_close = data.iloc[idx - 1]['close'] if idx > 0 else open_p
        change = close - prev_close
        change_pct = change / prev_close * 100 if prev_close != 0 else 0
        change_color = "#d32f2f" if change >= 0 else "#388e3c"
        change_text = f"{change:+.2f}({change_pct:+.2f}%)" if change != 0 else f"{change:.2f}(0.00%)"
        
        # 振幅 = (最高-最低)/昨收*100
        amplitude = (high - low) / prev_close * 100 if prev_close != 0 else 0
        
        labels['日期'].config(text=date_str)
        labels['开盘'].config(text=f"{open_p:.2f}")
        labels['最高'].config(text=f"{high:.2f}")
        labels['最低'].config(text=f"{low:.2f}")
        labels['收盘'].config(text=f"{close:.2f}")
        labels['成交量'].config(text=f"{volume:,.0f}")
        labels['振幅'].config(text=f"{amplitude:.2f}%")
        labels['涨跌'].config(text=change_text, fg=change_color)
        
        self.kline_last_index = idx
    
    def _trades_on_kline(self, idx):
        """获取该K线当日的成交记录列表"""
        if self.kline_data is None or not self.kline_trades:
            return []
        try:
            bar_date = self.kline_data.iloc[idx]['date']
            if hasattr(bar_date, 'date'):
                bar_date = bar_date.date()
            trades = []
            for t in self.kline_trades:
                tdate = t.timestamp
                if hasattr(tdate, 'date'):
                    tdate = tdate.date()
                if tdate == bar_date:
                    trades.append(t)
            return trades
        except Exception:
            return []
    
    def _fit_kline_figure(self):
        """使matplotlib Figure适配容器尺寸"""
        if self.kline_fig is None or self.kline_canvas is None:
            return
        try:
            w = self.kline_chart_frame.winfo_width()
            h = self.kline_chart_frame.winfo_height()
            if w < 100 or h < 100:
                return
            dpi = self.kline_fig.dpi
            # 仅当尺寸变化显著时重设，避免循环抖动
            if abs(self.kline_fig.get_figwidth() * dpi - w) > 8 or abs(self.kline_fig.get_figheight() * dpi - h) > 8:
                self.kline_fig.set_size_inches(w / dpi, h / dpi, forward=False)
                self.kline_fig.tight_layout()
                # 背景缓存失效：下次blit时重新整图绘制并缓存
                self._kline_bg = None
                self._set_all_markers_off()
                self.kline_canvas.draw_idle()
                self.root.after(30, self._capture_kline_bg)
        except Exception:
            pass
        
    def _draw_chart(self, chart_type, parent, image_path):
        """绘制图表到canvas"""
        try:
            # 等待窗口更新以获取正确的尺寸
            self.root.update_idletasks()
            parent.update_idletasks()
            
            # 加载图片
            img = Image.open(image_path)
            
            # 获取notebook的实际尺寸
            canvas_width = max(self.notebook.winfo_width() - 30, 1000)
            canvas_height = max(self.notebook.winfo_height() - 60, 700)
            
            # 计算缩放比例（放大铺满）
            ratio = min(canvas_width / img.width, canvas_height / img.height)
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 创建Canvas完全铺满窗口
            canvas = tk.Canvas(parent, highlightthickness=0)
            canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
            
            photo = ImageTk.PhotoImage(img)
            canvas.create_image(canvas_width//2, canvas_height//2, anchor=tk.CENTER, image=photo)
            canvas.image = photo  # 保持引用
            
            setattr(self, f"chart_canvas_{chart_type}", canvas)
            
        except Exception as e:
            self.log(f"显示图表失败: {e}")
            
    def on_window_resize(self, event):
        """窗口大小变化时重绘图表"""
        # 只处理主窗口大小变化
        if event.widget == self.root:
            for chart_type in ["equity", "monthly", "drawdown", "trades"]:
                chart_path = getattr(self, f"chart_path_{chart_type}", None)
                if chart_path and os.path.exists(chart_path):
                    label = getattr(self, f"chart_label_{chart_type}", None)
                    parent = label.master if label else None
                    if parent:
                        self._draw_chart(chart_type, parent, chart_path)
            
            # K线图自适应重绘
            if hasattr(self, 'kline_canvas') and self.kline_canvas is not None:
                self.root.after(80, self._fit_kline_figure)
            
    def run_backtest(self):
        """运行回测"""
        try:
            config = self.get_config()
        except Exception as e:
            messagebox.showerror("配置错误", f"配置参数有误: {e}")
            return
        
        # 禁用按钮
        self.run_btn.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self.update_status("正在运行回测...")
        
        # 在新线程中运行
        thread = threading.Thread(target=self._run_backtest_thread, args=(config,), daemon=True)
        thread.start()
        
    def _run_backtest_thread(self, config):
        """回测线程"""
        try:
            self.log("=" * 50)
            self.log("开始回测...")
            self.log(f"合约: {config.symbol}  策略: {config.strategy_name}")
            self.log(f"时间范围: {config.start_date} 至 {config.end_date}")
            
            # 1. 获取数据
            self.log("正在获取数据...")
            self.root.after(0, lambda: self.progress.configure(value=10))
            
            data_handler = get_data_handler(config.data_source)
            data = data_handler.get_futures_data(
                symbol=config.symbol,
                start_date=config.start_date,
                end_date=config.end_date
            )
            
            if data.empty:
                self.root.after(0, lambda: messagebox.showerror("错误", "无法获取数据"))
                self.root.after(0, lambda: self.run_btn.config(state=tk.NORMAL))
                return
            
            self.log(f"获取到 {len(data)} 条数据")
            self.root.after(0, lambda: self.progress.configure(value=30))
            
            # 2. 初始化引擎
            engine = BacktestEngine(
                initial_capital=config.initial_capital,
                commission_rate=config.commission_rate,
                slippage=config.slippage,
                margin_ratio=config.margin_ratio,
                contract_multiplier=300
            )
            engine.load_data(data)
            
            # 3. 加载策略
            strategy = get_strategy(config.strategy_name, config.strategy_params)
            self.log(f"策略加载完成")
            self.root.after(0, lambda: self.progress.configure(value=40))
            
            # 4. 运行回测
            self.log("正在回测...")
            
            def progress_callback(p):
                self.root.after(0, lambda p=p: self.progress.configure(value=40 + p * 0.3))
            
            equity_df = engine.run(strategy, progress_callback)
            self.root.after(0, lambda: self.progress.configure(value=70))
            
            # 5. 计算绩效
            self.log("计算绩效指标...")
            analyzer = PerformanceAnalyzer()
            metrics = analyzer.calculate_metrics(
                equity_df,
                engine.portfolio.trades,
                config.initial_capital
            )
            self.root.after(0, lambda: self.progress.configure(value=80))
            
            # 6. 生成图表
            self.log("生成可视化图表...")
            os.makedirs("output", exist_ok=True)
            visualizer = Visualizer("output")
            charts = visualizer.generate_all_charts(
                equity_df,
                engine.portfolio.trades,
                prefix=config.strategy_name,
                kline_data=data,
                symbol=config.symbol,
                strategy_name=config.strategy_name,
                strategy_params=config.strategy_params
            )
            
            # 保存K线数据用于交互式显示
            self.kline_data = data
            self.kline_trades = engine.portfolio.trades
            self.kline_strategy_name = config.strategy_name
            self.kline_strategy_params = config.strategy_params
            self.root.after(0, lambda: self.progress.configure(value=95))
            
            # 7. 更新界面（在主线程中）
            self.root.after(0, lambda: self._update_ui(metrics, engine.portfolio.trades, charts))
            
            self.log("回测完成!")
            self.root.after(0, lambda: self.progress.configure(value=100))
            self.root.after(0, lambda: self.update_status("回测完成"))
            
        except Exception as e:
            self.log(f"回测出错: {e}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"回测失败: {e}"))
        finally:
            self.root.after(0, lambda: self.run_btn.config(state=tk.NORMAL))
            
    def _update_ui(self, metrics, trades, charts):
        """更新UI界面"""
        # 更新绩效指标
        self.update_metrics(metrics)
        self.update_trade_summary(metrics, trades)
        self.update_trades_table(trades)
        
        # 显示图表
        for chart_type, chart_path in charts.items():
            if chart_path and os.path.exists(chart_path):
                if chart_type == "kline":
                    kline_data = getattr(self, 'kline_data', None)
                    self.display_chart(chart_type, chart_path, kline_data)
                else:
                    self.display_chart(chart_type, chart_path)
                
    def save_config(self):
        """保存配置"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json")],
            initialfile="backtest_config.json"
        )
        if filepath:
            try:
                config = self.get_config()
                import json
                data = {
                    'data_source': config.data_source,
                    'symbol': config.symbol,
                    'start_date': config.start_date,
                    'end_date': config.end_date,
                    'initial_capital': config.initial_capital,
                    'margin_ratio': config.margin_ratio,
                    'commission_rate': config.commission_rate,
                    'slippage': config.slippage,
                    'strategy_name': config.strategy_name,
                    'strategy_params': config.strategy_params,
                }
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("成功", "配置已保存")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}")
                
    def load_config(self):
        """加载配置"""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON文件", "*.json")]
        )
        if filepath:
            try:
                import json
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 更新界面
                self.data_source.set(data.get('data_source', 'akshare'))
                self.symbol.delete(0, tk.END)
                self.symbol.insert(0, data.get('symbol', 'IF0'))
                self.start_date.delete(0, tk.END)
                self.start_date.insert(0, data.get('start_date', '2025-09-01'))
                self.end_date.delete(0, tk.END)
                self.end_date.insert(0, data.get('end_date', '2026-09-01'))
                self.initial_capital.delete(0, tk.END)
                self.initial_capital.insert(0, str(data.get('initial_capital', 1000000)))
                self.margin_ratio.delete(0, tk.END)
                self.margin_ratio.insert(0, str(data.get('margin_ratio', 0.12)))
                self.commission_rate.delete(0, tk.END)
                self.commission_rate.insert(0, str(data.get('commission_rate', 0.000023)))
                self.slippage.delete(0, tk.END)
                self.slippage.insert(0, str(data.get('slippage', 0.2)))
                
                strategy = data.get('strategy_name', 'bollinger')
                self.strategy_name.set(strategy)
                self.create_strategy_params(strategy)
                self.update_strategy_desc(strategy)
                
                # 更新策略参数
                params = data.get('strategy_params', {})
                for key, value in params.items():
                    if key in self.param_entries:
                        self.param_entries[key].delete(0, tk.END)
                        self.param_entries[key].insert(0, str(value))
                
                messagebox.showinfo("成功", "配置已加载")
            except Exception as e:
                messagebox.showerror("错误", f"加载失败: {e}")
                
    def export_trades(self):
        """导出交易记录"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv")],
            initialfile="trades.csv"
        )
        if filepath:
            try:
                # 从表格中获取数据
                items = self.trades_tree.get_children()
                data = []
                for item in items:
                    values = self.trades_tree.item(item)['values']
                    data.append(values)
                
                if data:
                    columns = ["trade_id", "action", "side", "price", "quantity", "timestamp", "commission", "pnl_points", "pnl_amount", "pnl_percent"]
                    df = pd.DataFrame(data, columns=columns)
                    df.to_csv(filepath, index=False, encoding='utf-8-sig')
                    messagebox.showinfo("成功", f"已导出 {len(data)} 条记录")
                else:
                    messagebox.showwarning("警告", "没有可导出的数据")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")


def main():
    root = tk.Tk()
    app = BacktestGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

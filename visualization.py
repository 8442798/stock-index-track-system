"""
可视化模块 - 生成回测结果的图表
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端，避免线程问题
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Dict, List, Optional
from datetime import datetime
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class Visualizer:
    """可视化工具类"""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def plot_equity_curve(
        self,
        equity_df: pd.DataFrame,
        benchmark_df: pd.DataFrame = None,
        title: str = "权益曲线",
        save_path: str = None
    ):
        """
        绘制权益曲线
        
        Args:
            equity_df: 权益曲线数据
            benchmark_df: 基准数据（可选）
            title: 图表标题
            save_path: 保存路径
        """
        fig, axes = plt.subplots(2, 1, figsize=(18, 10), gridspec_kw={'height_ratios': [3, 1]})
        
        # 权益曲线
        ax1 = axes[0]
        ax1.plot(equity_df['date'], equity_df['equity'], label='策略权益', linewidth=2)
        
        if benchmark_df is not None and not benchmark_df.empty:
            # 归一化基准
            benchmark_normalized = benchmark_df['close'] / benchmark_df['close'].iloc[0] * equity_df['equity'].iloc[0]
            ax1.plot(benchmark_df['date'], benchmark_normalized, label='基准', linewidth=1, alpha=0.7)
        
        ax1.set_title(title, fontsize=14)
        ax1.set_ylabel('权益 (元)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        
        # 回撤曲线
        ax2 = axes[1]
        peak = equity_df['equity'].expanding().max()
        drawdown = (equity_df['equity'] - peak) / peak * 100
        ax2.fill_between(equity_df['date'], drawdown, 0, alpha=0.5, color='red')
        ax2.set_ylabel('回撤 (%)')
        ax2.set_xlabel('日期')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
        else:
            save_path = os.path.join(self.output_dir, 'equity_curve.png')
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
        
        plt.close()
        return save_path
    
    def plot_monthly_returns(
        self,
        equity_df: pd.DataFrame,
        title: str = "月度收益分布",
        save_path: str = None
    ):
        """
        绘制月度收益热力图
        """
        # 计算月度收益
        equity_df = equity_df.copy()
        equity_df['date'] = pd.to_datetime(equity_df['date'])
        equity_df.set_index('date', inplace=True)
        
        monthly_returns = equity_df['equity'].resample('ME').last().pct_change().dropna()
        
        # 转换为年-月格式
        monthly_df = pd.DataFrame({
            'year': monthly_returns.index.year,
            'month': monthly_returns.index.month,
            'return': monthly_returns.values * 100
        })
        
        # 创建透视表
        pivot_table = monthly_df.pivot_table(
            values='return',
            index='year',
            columns='month',
            aggfunc='first'
        )
        
        fig, ax = plt.subplots(figsize=(16, 8))
        
        # 绘制热力图
        im = ax.imshow(pivot_table.values, cmap='RdYlGn', aspect='auto')
        
        # 设置坐标轴
        ax.set_xticks(range(12))
        ax.set_xticklabels([f'{m}月' for m in range(1, 13)])
        ax.set_yticks(range(len(pivot_table.index)))
        ax.set_yticklabels(pivot_table.index)
        
        # 添加数值标注
        for i in range(len(pivot_table.index)):
            for j in range(12):
                if j + 1 in pivot_table.columns:
                    value = pivot_table.iloc[i, pivot_table.columns.get_loc(j + 1)]
                    if not np.isnan(value):
                        color = 'white' if abs(value) > 5 else 'black'
                        ax.text(j, i, f'{value:.1f}%', ha='center', va='center', color=color)
        
        plt.colorbar(im, label='收益率 (%)')
        ax.set_title(title, fontsize=14)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
        else:
            save_path = os.path.join(self.output_dir, 'monthly_returns.png')
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
        
        plt.close()
        return save_path
    
    def plot_drawdown_analysis(
        self,
        equity_df: pd.DataFrame,
        title: str = "回撤分析",
        save_path: str = None
    ):
        """
        绘制回撤分析图
        """
        fig, axes = plt.subplots(2, 1, figsize=(16, 10))
        
        # 计算回撤
        peak = equity_df['equity'].expanding().max()
        drawdown = (equity_df['equity'] - peak) / peak * 100
        
        # 回撤曲线
        ax1 = axes[0]
        ax1.fill_between(equity_df['date'], drawdown, 0, alpha=0.7, color='red')
        ax1.set_title(f'{title} - 回撤曲线', fontsize=12)
        ax1.set_ylabel('回撤 (%)')
        ax1.grid(True, alpha=0.3)
        
        # 回撤分布直方图
        ax2 = axes[1]
        ax2.hist(drawdown[drawdown < 0], bins=50, color='red', alpha=0.7, edgecolor='black')
        ax2.set_title('回撤分布', fontsize=12)
        ax2.set_xlabel('回撤 (%)')
        ax2.set_ylabel('频次')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
        else:
            save_path = os.path.join(self.output_dir, 'drawdown_analysis.png')
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
        
        plt.close()
        return save_path
    
    def plot_trade_analysis(
        self,
        trades: List,
        title: str = "交易分析",
        save_path: str = None
    ):
        """
        绘制交易分析图
        """
        if not trades:
            return None
        
        # 提取交易数据
        trade_data = []
        for trade in trades:
            if hasattr(trade, 'side'):
                trade_data.append({
                    'date': trade.timestamp,
                    'side': trade.side.value,
                    'action': trade.action,
                    'price': trade.price,
                    'quantity': trade.quantity
                })
        
        if not trade_data:
            return None
        
        trade_df = pd.DataFrame(trade_data)
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        
        # 操作类型分布
        ax1 = axes[0, 0]
        action_counts = trade_df['action'].value_counts()
        color_map = {'开多': 'green', '开空': 'red', '平多': 'orange', '平空': 'cyan'}
        colors = [color_map.get(a, 'gray') for a in action_counts.index]
        ax1.bar(action_counts.index, action_counts.values, color=colors)
        ax1.set_title('操作类型分布')
        ax1.set_ylabel('次数')
        
        # 交易时间分布（按日期的天）
        ax2 = axes[0, 1]
        trade_df['date_only'] = pd.to_datetime(trade_df['date']).dt.date
        date_counts = trade_df['date_only'].value_counts().sort_index()
        ax2.bar(range(len(date_counts)), date_counts.values)
        ax2.set_title('交易日期分布')
        ax2.set_xlabel('交易日序号')
        ax2.set_ylabel('次数')
        
        # 开仓价格分布
        ax3 = axes[1, 0]
        buy_prices = trade_df[trade_df['side'] == 'buy']['price']
        sell_prices = trade_df[trade_df['side'] == 'sell']['price']
        if len(buy_prices) > 0:
            ax3.hist(buy_prices, bins=20, alpha=0.6, label='开多', color='green')
        if len(sell_prices) > 0:
            ax3.hist(sell_prices, bins=20, alpha=0.6, label='开空', color='red')
        ax3.set_title('开仓价格分布')
        ax3.set_xlabel('价格')
        ax3.set_ylabel('频次')
        ax3.legend()
        
        # 累计交易数量
        ax4 = axes[1, 1]
        trade_df['cumulative_qty'] = trade_df['quantity'].cumsum()
        ax4.plot(range(len(trade_df)), trade_df['cumulative_qty'], marker='o', markersize=4)
        ax4.set_title('累计交易数量')
        ax4.set_xlabel('交易序号')
        ax4.set_ylabel('累计数量')
        ax4.grid(True, alpha=0.3)
        
        plt.suptitle(title, fontsize=14)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
        else:
            save_path = os.path.join(self.output_dir, 'trade_analysis.png')
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
        
        plt.close()
        return save_path
    
    def plot_kline(
        self,
        data: pd.DataFrame,
        trades: List = None,
        title: str = "日K线图",
        save_path: str = None
    ):
        """
        绘制日K线图，标记买卖交易点
        
        Args:
            data: OHLCV数据
            trades: 交易记录列表
            title: 图表标题
            save_path: 保存路径
        """
        if data is None or data.empty:
            return None
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 10), 
                                         gridspec_kw={'height_ratios': [3, 1]},
                                         sharex=True)
        
        # K线图
        dates = range(len(data))
        width = 0.6
        
        for i, (idx, row) in enumerate(data.iterrows()):
            color = '#d32f2f' if row['close'] >= row['open'] else '#388e3c'
            
            # 实体（矩形）
            body_low = min(row['open'], row['close'])
            body_high = max(row['open'], row['close'])
            body_height = body_high - body_low
            if body_height == 0:
                body_height = 0.1
            
            rect = plt.Rectangle((i - width/2, body_low), width, body_height,
                               facecolor=color, edgecolor=color, linewidth=0.8)
            ax1.add_patch(rect)
            
            # 上下影线
            ax1.plot([i, i], [body_high, row['high']], color=color, linewidth=0.8)
            ax1.plot([i, i], [body_low, row['low']], color=color, linewidth=0.8)
        
        # 标记交易点
        if trades:
            trade_dates = []
            trade_prices = []
            trade_colors = []
            trade_markers = []
            trade_labels = []
            
            for trade in trades:
                # 找到交易日期对应的K线位置
                trade_date = trade.timestamp
                if hasattr(trade_date, 'date'):
                    trade_date = trade_date.date()
                
                for j, (idx, row) in enumerate(data.iterrows()):
                    row_date = row['date']
                    if hasattr(row_date, 'date'):
                        row_date = row_date.date()
                    
                    if row_date == trade_date:
                        trade_dates.append(j)
                        trade_prices.append(trade.price)
                        trade_labels.append(trade.action)
                        
                        if trade.action == '开多':
                            trade_colors.append('#1565C0')  # 深蓝色
                            trade_markers.append('^')
                        elif trade.action == '平多':
                            trade_colors.append('#E65100')  # 深橙色
                            trade_markers.append('v')
                        elif trade.action == '开空':
                            trade_colors.append('#6A1B9A')  # 深紫色
                            trade_markers.append('v')
                        elif trade.action == '平空':
                            trade_colors.append('#00838F')  # 深青色
                            trade_markers.append('^')
                        else:
                            trade_colors.append('gray')
                            trade_markers.append('o')
                        break
            
            # 绘制交易标记（大尺寸+黑色粗边框）
            for x, y, c, m, label in zip(trade_dates, trade_prices, trade_colors, trade_markers, trade_labels):
                ax1.scatter(x, y, color=c, marker=m, s=220, zorder=5, 
                           edgecolors='black', linewidth=1.5)
                # 添加文字标注
                offset_y = 15 if m == '^' else -15
                ax1.annotate(label, (x, y), textcoords="offset points", 
                            xytext=(0, offset_y), ha='center', fontsize=7,
                            fontweight='bold', color=c,
                            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                     edgecolor=c, alpha=0.9))
            
            # 添加图例
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor='#1565C0', edgecolor='black', label='开多'),
                Patch(facecolor='#E65100', edgecolor='black', label='平多'),
                Patch(facecolor='#6A1B9A', edgecolor='black', label='开空'),
                Patch(facecolor='#00838F', edgecolor='black', label='平空'),
            ]
            ax1.legend(handles=legend_elements, loc='upper left', fontsize=8, 
                      framealpha=0.9, edgecolor='black')
        
        # 添加均线
        if len(data) >= 20:
            ma20 = data['close'].rolling(window=20).mean()
            ax1.plot(dates, ma20, color='blue', linewidth=1, alpha=0.7, label='MA20')
        if len(data) >= 60:
            ma60 = data['close'].rolling(window=60).mean()
            ax1.plot(dates, ma60, color='purple', linewidth=1, alpha=0.7, label='MA60')
        
        ax1.set_title(title, fontsize=14)
        ax1.set_ylabel('价格')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 成交量
        for i, (idx, row) in enumerate(data.iterrows()):
            color = '#d32f2f' if row['close'] >= row['open'] else '#388e3c'
            ax2.bar(i, row['volume'], width=width, color=color, alpha=0.7)
        
        ax2.set_ylabel('成交量')
        ax2.set_xlabel('日期')
        ax2.grid(True, alpha=0.3)
        
        # 设置x轴刻度
        tick_interval = max(1, len(data) // 20)
        tick_positions = list(range(0, len(data), tick_interval))
        tick_labels = [str(data.iloc[i]['date'])[:10] for i in tick_positions]
        ax2.set_xticks(tick_positions)
        ax2.set_xticklabels(tick_labels, rotation=45, fontsize=8)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
        else:
            save_path = os.path.join(self.output_dir, 'kline.png')
            plt.savefig(save_path, dpi=200, bbox_inches='tight')
        
        plt.close()
        return save_path
    
    def generate_all_charts(
        self,
        equity_df: pd.DataFrame,
        trades: List,
        benchmark_df: pd.DataFrame = None,
        prefix: str = "backtest",
        kline_data: pd.DataFrame = None,
        symbol: str = ""
    ) -> Dict[str, str]:
        """
        生成所有图表
        
        Returns:
            图表文件路径字典
        """
        charts = {}
        
        # 权益曲线
        charts['equity'] = self.plot_equity_curve(
            equity_df,
            benchmark_df,
            save_path=os.path.join(self.output_dir, f'{prefix}_equity.png')
        )
        
        # 月度收益
        charts['monthly'] = self.plot_monthly_returns(
            equity_df,
            save_path=os.path.join(self.output_dir, f'{prefix}_monthly.png')
        )
        
        # 回撤分析
        charts['drawdown'] = self.plot_drawdown_analysis(
            equity_df,
            save_path=os.path.join(self.output_dir, f'{prefix}_drawdown.png')
        )
        
        # 交易分析
        if trades:
            charts['trades'] = self.plot_trade_analysis(
                trades,
                save_path=os.path.join(self.output_dir, f'{prefix}_trades.png')
            )
        
        # K线图
        if kline_data is not None and not kline_data.empty:
            title = f"{symbol} {prefix} 日K线图" if symbol else f"{prefix} 日K线图"
            charts['kline'] = self.plot_kline(
                kline_data,
                trades,
                title=title,
                save_path=os.path.join(self.output_dir, f'{prefix}_kline.png')
            )
        
        return charts

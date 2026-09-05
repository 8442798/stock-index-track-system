"""
绩效统计模块 - 计算回测的各项绩效指标
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PerformanceMetrics:
    """绩效指标数据类"""
    # 收益指标
    total_return: float = 0.0
    annual_return: float = 0.0
    monthly_return: float = 0.0
    
    # 风险指标
    volatility: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    
    # 风险调整收益
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # 交易统计
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    
    # 平均盈亏
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0


class PerformanceAnalyzer:
    """绩效分析器"""
    
    def __init__(self, risk_free_rate: float = 0.03):
        """
        Args:
            risk_free_rate: 无风险利率（年化），默认3%
        """
        self.risk_free_rate = risk_free_rate
        
    def calculate_metrics(
        self,
        equity_df: pd.DataFrame,
        trades: List = None,
        initial_capital: float = 1000000.0
    ) -> PerformanceMetrics:
        """
        计算绩效指标
        
        Args:
            equity_df: 权益曲线DataFrame，包含date和equity列
            trades: 交易记录列表
            initial_capital: 初始资金
            
        Returns:
            PerformanceMetrics实例
        """
        metrics = PerformanceMetrics()
        
        if equity_df is None or equity_df.empty:
            return metrics
        
        # 计算收益指标
        metrics.total_return = (equity_df['equity'].iloc[-1] / initial_capital) - 1
        
        # 计算年化收益率
        days = (equity_df['date'].iloc[-1] - equity_df['date'].iloc[0]).days
        if days > 0 and metrics.total_return > -1:
            metrics.annual_return = (1 + metrics.total_return) ** (365 / days) - 1
        
        # 计算波动率
        if 'returns' in equity_df.columns:
            metrics.volatility = equity_df['returns'].std() * np.sqrt(252)
        
        # 计算最大回撤
        metrics.max_drawdown, metrics.max_drawdown_duration = self._calculate_max_drawdown(
            equity_df['equity']
        )
        
        # 计算风险调整收益
        if metrics.volatility > 0:
            metrics.sharpe_ratio = (metrics.annual_return - self.risk_free_rate) / metrics.volatility
            
            # Sortino比率（只考虑下行波动）
            downside_returns = equity_df['returns'][equity_df['returns'] < 0]
            if len(downside_returns) > 0:
                downside_vol = downside_returns.std() * np.sqrt(252)
                if downside_vol > 0:
                    metrics.sortino_ratio = (metrics.annual_return - self.risk_free_rate) / downside_vol
        
        if metrics.max_drawdown > 0:
            metrics.calmar_ratio = metrics.annual_return / metrics.max_drawdown
        
        # 计算交易统计
        if trades:
            metrics = self._calculate_trade_metrics(metrics, trades)
        
        return metrics
    
    def _calculate_max_drawdown(self, equity_series: pd.Series) -> tuple:
        """计算最大回撤和回撤持续时间"""
        peak = equity_series.expanding(min_periods=1).max()
        drawdown = (equity_series - peak) / peak
        
        max_dd = abs(drawdown.min())
        
        # 计算回撤持续时间
        is_drawdown = drawdown < 0
        drawdown_groups = (~is_drawdown).cumsum()
        
        max_duration = 0
        if is_drawdown.any():
            for _, group in drawdown.groupby(drawdown_groups):
                if group.iloc[0] < 0:
                    duration = len(group)
                    max_duration = max(max_duration, duration)
        
        return max_dd, max_duration
    
    def _calculate_trade_metrics(self, metrics: PerformanceMetrics, trades: List) -> PerformanceMetrics:
        """计算交易统计指标 - 按开平仓配对计算"""
        if not trades:
            return metrics
        
        metrics.total_trades = len(trades)
        
        # 配对交易计算盈亏（买+卖=一组完整交易）
        profits = []
        losses = []
        open_price = None
        open_side = None
        
        for trade in trades:
            if trade.side.value == 'buy':
                if open_price is None:
                    # 开仓
                    open_price = trade.price
                    open_side = 'buy'
                elif open_side == 'sell':
                    # 平空仓
                    pnl = (open_price - trade.price) * trade.quantity * 300 - trade.commission
                    if pnl > 0:
                        profits.append(pnl)
                    else:
                        losses.append(abs(pnl))
                    open_price = None
                    open_side = None
            elif trade.side.value == 'sell':
                if open_price is None:
                    # 开仓
                    open_price = trade.price
                    open_side = 'sell'
                elif open_side == 'buy':
                    # 平多仓
                    pnl = (trade.price - open_price) * trade.quantity * 300 - trade.commission
                    if pnl > 0:
                        profits.append(pnl)
                    else:
                        losses.append(abs(pnl))
                    open_price = None
                    open_side = None
        
        metrics.winning_trades = len(profits)
        metrics.losing_trades = len(losses)
        
        total_round_trips = len(profits) + len(losses)
        if total_round_trips > 0:
            metrics.win_rate = len(profits) / total_round_trips
        
        if profits:
            metrics.avg_profit = np.mean(profits)
        if losses:
            metrics.avg_loss = np.mean(losses)
        
        if losses and sum(losses) > 0:
            metrics.profit_factor = sum(profits) / sum(losses)
        
        # 计算最大连续盈亏（按round trip）
        all_pnls = profits + [-l for l in losses]
        max_count = 0
        current_count = 0
        for pnl in all_pnls:
            if pnl > 0:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        metrics.max_consecutive_wins = max_count
        
        max_count = 0
        current_count = 0
        for pnl in all_pnls:
            if pnl < 0:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        metrics.max_consecutive_losses = max_count
        
        return metrics
    
    def print_report(self, metrics: PerformanceMetrics):
        """打印绩效报告"""
        print("\n" + "="*60)
        print("                  回测绩效报告")
        print("="*60)
        
        print("\n【收益指标】")
        print(f"  总收益率:      {metrics.total_return:.2%}")
        print(f"  年化收益率:    {metrics.annual_return:.2%}")
        
        print("\n【风险指标】")
        print(f"  年化波动率:    {metrics.volatility:.2%}")
        print(f"  最大回撤:      {metrics.max_drawdown:.2%}")
        print(f"  回撤持续天数:  {metrics.max_drawdown_duration} 天")
        
        print("\n【风险调整收益】")
        print(f"  夏普比率:      {metrics.sharpe_ratio:.2f}")
        print(f"  索提诺比率:    {metrics.sortino_ratio:.2f}")
        print(f"  卡玛比率:      {metrics.calmar_ratio:.2f}")
        
        print("\n【交易统计】")
        print(f"  总交易次数:    {metrics.total_trades}")
        print(f"  盈利次数:      {metrics.winning_trades}")
        print(f"  亏损次数:      {metrics.losing_trades}")
        print(f"  胜率:          {metrics.win_rate:.2%}")
        print(f"  盈亏比:        {metrics.profit_factor:.2f}")
        
        print("\n【平均盈亏】")
        print(f"  平均盈利:      {metrics.avg_profit:,.2f}")
        print(f"  平均亏损:      {metrics.avg_loss:,.2f}")
        print(f"  最大连胜:      {metrics.max_consecutive_wins}")
        print(f"  最大连亏:      {metrics.max_consecutive_losses}")
        
        print("\n" + "="*60)

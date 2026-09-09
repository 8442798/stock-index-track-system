"""
策略模块 - 包含多个经典量化策略示例
"""
import pandas as pd
import numpy as np
from typing import Dict, List
from engine import Strategy, BacktestEngine, OrderSide, OrderType


class DualMAStrategy(Strategy):
    """
    双均线策略
    当短期均线上穿长期均线时做多，下穿时做空
    """
    
    def __init__(self, params: Dict = None):
        default_params = {
            'short_window': 5,   # 短期均线周期
            'long_window': 20,   # 长期均线周期
            'position_size': 1   # 持仓手数
        }
        if params:
            default_params.update(params)
        super().__init__(default_params)
        
        self.short_ma = []
        self.long_ma = []
        self.current_position = 0  # 1: 多头, -1: 空头, 0: 空仓
        
    def on_bar(self, engine: BacktestEngine, bar: Dict):
        # 收集价格数据
        self.short_ma.append(bar['close'])
        self.long_ma.append(bar['close'])
        
        # 数据不足，跳过
        if len(self.long_ma) < self.params['long_window']:
            return
        
        # 计算均线
        short_ma_value = np.mean(self.short_ma[-self.params['short_window']:])
        long_ma_value = np.mean(self.long_ma[-self.params['long_window']:])
        
        # 从引擎获取当前持仓（正数=多头，负数=空头，0=空仓）
        current_position = 0
        if engine.portfolio.positions:
            pos = list(engine.portfolio.positions.values())[0]
            current_position = pos.quantity if pos.side.value == 'long' else -pos.quantity
        
        # 交易逻辑
        if short_ma_value > long_ma_value and current_position <= 0:
            # 金叉 - 开多
            if current_position < 0:
                # 先平空
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.BUY,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
                current_position = 0  # 更新本地持仓状态
            # 开多
            engine.submit_order(
                symbol='IF',
                side=OrderSide.BUY,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET
            )
            
        elif short_ma_value < long_ma_value and current_position >= 0:
            # 死叉 - 开空
            if current_position > 0:
                # 先平多
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.SELL,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
                current_position = 0  # 更新本地持仓状态
            # 开空
            engine.submit_order(
                symbol='IF',
                side=OrderSide.SELL,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET
            )


class MACrossStrategy(Strategy):
    """
    均线交叉策略 - 支持止盈止损
    """
    
    def __init__(self, params: Dict = None):
        default_params = {
            'fast_period': 10,
            'slow_period': 30,
            'stop_loss': 0.02,    # 止损比例 2%
            'take_profit': 0.05,  # 止盈比例 5%
            'position_size': 1
        }
        if params:
            default_params.update(params)
        super().__init__(default_params)
        
        self.prices = []
        self.entry_price = 0
        
    def _get_position(self, engine):
        """从引擎获取当前持仓（正数=多头，负数=空头，0=空仓）"""
        if engine.portfolio.positions:
            pos = list(engine.portfolio.positions.values())[0]
            return pos.quantity if pos.side.value == 'long' else -pos.quantity
        return 0
        
    def on_bar(self, engine: BacktestEngine, bar: Dict):
        self.prices.append(bar['close'])
        
        if len(self.prices) < self.params['slow_period']:
            return
        
        # 计算均线
        fast_ma = np.mean(self.prices[-self.params['fast_period']:])
        slow_ma = np.mean(self.prices[-self.params['slow_period']:])
        
        current_price = bar['close']
        
        # 从引擎获取当前持仓
        current_position = self._get_position(engine)
        
        # 止盈止损检查
        if current_position != 0 and self.entry_price > 0:
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            
            if current_position > 0:  # 多头
                if pnl_pct <= -self.params['stop_loss'] or pnl_pct >= self.params['take_profit']:
                    engine.submit_order(
                        symbol='IF',
                        side=OrderSide.SELL,
                        quantity=abs(current_position),
                        order_type=OrderType.MARKET
                    )
                    self.entry_price = 0
                    return
            else:  # 空头
                if pnl_pct >= self.params['stop_loss'] or pnl_pct <= -self.params['take_profit']:
                    engine.submit_order(
                        symbol='IF',
                        side=OrderSide.BUY,
                        quantity=abs(current_position),
                        order_type=OrderType.MARKET
                    )
                    self.entry_price = 0
                    return
        
        # 交易信号
        if fast_ma > slow_ma and current_position <= 0:
            if current_position < 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.BUY,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
            engine.submit_order(
                symbol='IF',
                side=OrderSide.BUY,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET
            )
            self.entry_price = current_price
            
        elif fast_ma < slow_ma and current_position >= 0:
            if current_position > 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.SELL,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
            engine.submit_order(
                symbol='IF',
                side=OrderSide.SELL,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET
            )
            self.entry_price = current_price


class BollingerBandStrategy(Strategy):
    """
    布林带策略
    价格触及下轨做多，触及上轨做空
    """
    
    def __init__(self, params: Dict = None):
        default_params = {
            'window': 20,
            'num_std': 2.0,
            'position_size': 1
        }
        if params:
            default_params.update(params)
        super().__init__(default_params)
        
        self.prices = []
        
    def _get_position(self, engine):
        """从引擎获取当前持仓（正数=多头，负数=空头，0=空仓）"""
        if engine.portfolio.positions:
            pos = list(engine.portfolio.positions.values())[0]
            return pos.quantity if pos.side.value == 'long' else -pos.quantity
        return 0
        
    def on_bar(self, engine: BacktestEngine, bar: Dict):
        self.prices.append(bar['close'])
        
        if len(self.prices) < self.params['window']:
            return
        
        # 计算布林带
        window_data = self.prices[-self.params['window']:]
        middle_band = np.mean(window_data)
        std = np.std(window_data)
        upper_band = middle_band + self.params['num_std'] * std
        lower_band = middle_band - self.params['num_std'] * std
        
        current_price = bar['close']
        
        # 从引擎获取当前持仓
        current_position = self._get_position(engine)
        
        # 交易信号
        if current_price < lower_band and current_position <= 0:
            # 先平空，再开多
            if current_position < 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.BUY,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
                current_position = 0  # 更新本地持仓状态
            # 开多
            engine.submit_order(
                symbol='IF',
                side=OrderSide.BUY,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET
            )
            
        elif current_price > upper_band and current_position >= 0:
            # 先平多，再开空
            if current_position > 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.SELL,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
                current_position = 0  # 更新本地持仓状态
            # 开空
            engine.submit_order(
                symbol='IF',
                side=OrderSide.SELL,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET
            )
            
        # 回到中轨平仓
        elif abs(current_price - middle_band) / middle_band < 0.005 and current_position != 0:
            if current_position > 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.SELL,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
            else:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.BUY,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )


class RSIMeanReversionStrategy(Strategy):
    """
    RSI均值回归策略
    RSI超卖时做多，超买时做空
    """
    
    def __init__(self, params: Dict = None):
        default_params = {
            'rsi_period': 14,
            'oversold': 30,    # 超卖阈值
            'overbought': 70,  # 超买阈值
            'position_size': 1
        }
        if params:
            default_params.update(params)
        super().__init__(default_params)
        
        self.prices = []
        self.gains = []
        self.losses = []
        
    def _get_position(self, engine):
        """从引擎获取当前持仓（正数=多头，负数=空头，0=空仓）"""
        if engine.portfolio.positions:
            pos = list(engine.portfolio.positions.values())[0]
            return pos.quantity if pos.side.value == 'long' else -pos.quantity
        return 0
        
    def calculate_rsi(self) -> float:
        """计算RSI指标"""
        if len(self.gains) < self.params['rsi_period']:
            return 50  # 默认值
        
        avg_gain = np.mean(self.gains[-self.params['rsi_period']:])
        avg_loss = np.mean(self.losses[-self.params['rsi_period']:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def on_bar(self, engine: BacktestEngine, bar: Dict):
        current_price = bar['close']
        
        # 计算涨跌
        if self.prices:
            change = current_price - self.prices[-1]
            self.gains.append(max(change, 0))
            self.losses.append(abs(min(change, 0)))
        
        self.prices.append(current_price)
        
        # 计算RSI
        rsi = self.calculate_rsi()
        
        # 从引擎获取当前持仓
        current_position = self._get_position(engine)
        
        # 交易信号
        if rsi < self.params['oversold'] and current_position <= 0:
            if current_position < 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.BUY,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
            engine.submit_order(
                symbol='IF',
                side=OrderSide.BUY,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET
            )
            
        elif rsi > self.params['overbought'] and current_position >= 0:
            if current_position > 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.SELL,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
            engine.submit_order(
                symbol='IF',
                side=OrderSide.SELL,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET
            )


class MomentumBreakoutStrategy(Strategy):
    """
    动量突破策略
    价格突破N日高点做多，跌破N日低点做空
    """
    
    def __init__(self, params: Dict = None):
        default_params = {
            'lookback': 20,
            'position_size': 1
        }
        if params:
            default_params.update(params)
        super().__init__(default_params)
        
        self.highs = []
        self.lows = []
        
    def _get_position(self, engine):
        """从引擎获取当前持仓（正数=多头，负数=空头，0=空仓）"""
        if engine.portfolio.positions:
            pos = list(engine.portfolio.positions.values())[0]
            return pos.quantity if pos.side.value == 'long' else -pos.quantity
        return 0
        
    def on_bar(self, engine: BacktestEngine, bar: Dict):
        self.highs.append(bar['high'])
        self.lows.append(bar['low'])
        
        if len(self.highs) < self.params['lookback'] + 1:
            return
        
        # 计算N日高低点（排除当前bar）
        highest = max(self.highs[-(self.params['lookback']+1):-1])
        lowest = min(self.lows[-(self.params['lookback']+1):-1])
        
        current_price = bar['close']
        
        # 从引擎获取当前持仓
        current_position = self._get_position(engine)
        
        # 交易信号
        if current_price > highest and current_position <= 0:
            if current_position < 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.BUY,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
            engine.submit_order(
                symbol='IF',
                side=OrderSide.BUY,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET
            )
            
        elif current_price < lowest and current_position >= 0:
            if current_position > 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.SELL,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
            engine.submit_order(
                symbol='IF',
                side=OrderSide.SELL,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET
            )


class OvernightLimitShortStrategy(Strategy):
    """
    隔日极限做空策略
    以前一日收盘价+1%的价格开空单
    盈利5%或亏损2%时平仓
    """
    
    def __init__(self, params: Dict = None):
        default_params = {
            'position_size': 1,
            'entry_pct': 0.01,
            'take_profit': 0.05,
            'stop_loss': 0.02
        }
        if params:
            default_params.update(params)
        super().__init__(default_params)
        
        self.prev_close = None
        self.entry_price = None
    
    def _get_position(self, engine):
        """从引擎获取当前持仓（正数=多头，负数=空头，0=空仓）"""
        if engine.portfolio.positions:
            pos = list(engine.portfolio.positions.values())[0]
            return pos.quantity if pos.side.value == 'long' else -pos.quantity
        return 0
    
    def on_bar(self, engine: BacktestEngine, bar: Dict):
        current_price = bar['close']
        bar_high = bar['high']
        bar_low = bar['low']
        
        # 第一根bar，记录收盘价
        if self.prev_close is None:
            self.prev_close = current_price
            return
        
        current_position = self._get_position(engine)
        
        # 持仓中：检查止盈止损
        if current_position < 0 and self.entry_price is not None:
            # 盈利5%平仓：价格 <= 开仓价 * (1 - 5%)
            if bar_low <= self.entry_price * (1 - self.params['take_profit']):
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.BUY,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
                self.entry_price = None
                self.prev_close = current_price
                return
            
            # 亏损2%平仓：价格 >= 开仓价 * (1 + 2%)
            if bar_high >= self.entry_price * (1 + self.params['stop_loss']):
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.BUY,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET
                )
                self.entry_price = None
                self.prev_close = current_price
                return
        
        # 空仓：检查开空条件
        entry_price = self.prev_close * (1 + self.params['entry_pct'])
        if current_position == 0 and bar_high >= entry_price:
            engine.submit_order(
                symbol='IF',
                side=OrderSide.SELL,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET
            )
            self.entry_price = entry_price
            self.prev_close = current_price
            return
        
        # 无交易，更新收盘价
        self.prev_close = current_price


def get_strategy(strategy_name: str, params: Dict = None) -> Strategy:
    """
    工厂函数：根据策略名称返回策略实例
    
    Args:
        strategy_name: 策略名称
        params: 策略参数
        
    Returns:
        Strategy实例
    """
    strategies = {
        'dual_ma': DualMAStrategy,
        'ma_cross': MACrossStrategy,
        'bollinger': BollingerBandStrategy,
        'rsi': RSIMeanReversionStrategy,
        'momentum': MomentumBreakoutStrategy,
        'overnight_limit_short': OvernightLimitShortStrategy,
    }
    
    if strategy_name not in strategies:
        raise ValueError(f"未知策略: {strategy_name}，可选策略: {list(strategies.keys())}")
    
    return strategies[strategy_name](params)

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
                    order_type=OrderType.MARKET,
                    reason=f"双均线金叉({self.params['short_window']}/{self.params['long_window']})，平空转多"
                )
                current_position = 0  # 更新本地持仓状态
            # 开多
            engine.submit_order(
                symbol='IF',
                side=OrderSide.BUY,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET,
                reason=f"双均线金叉({self.params['short_window']}/{self.params['long_window']})，开多"
            )
            
        elif short_ma_value < long_ma_value and current_position >= 0:
            # 死叉 - 开空
            if current_position > 0:
                # 先平多
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.SELL,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET,
                    reason=f"双均线死叉({self.params['short_window']}/{self.params['long_window']})，平多转空"
                )
                current_position = 0  # 更新本地持仓状态
            # 开空
            engine.submit_order(
                symbol='IF',
                side=OrderSide.SELL,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET,
                reason=f"双均线死叉({self.params['short_window']}/{self.params['long_window']})，开空"
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
                if pnl_pct <= -self.params['stop_loss']:
                    engine.submit_order(
                        symbol='IF',
                        side=OrderSide.SELL,
                        quantity=abs(current_position),
                        order_type=OrderType.MARKET,
                        reason=f"多头止损({pnl_pct*100:.2f}%<=-{self.params['stop_loss']*100:.0f}%)"
                    )
                    self.entry_price = 0
                    return
                if pnl_pct >= self.params['take_profit']:
                    engine.submit_order(
                        symbol='IF',
                        side=OrderSide.SELL,
                        quantity=abs(current_position),
                        order_type=OrderType.MARKET,
                        reason=f"多头止盈({pnl_pct*100:.2f}%>={self.params['take_profit']*100:.0f}%)"
                    )
                    self.entry_price = 0
                    return
            else:  # 空头
                if pnl_pct >= self.params['stop_loss']:
                    engine.submit_order(
                        symbol='IF',
                        side=OrderSide.BUY,
                        quantity=abs(current_position),
                        order_type=OrderType.MARKET,
                        reason=f"空头止损({pnl_pct*100:.2f}%>={self.params['stop_loss']*100:.0f}%)"
                    )
                    self.entry_price = 0
                    return
                if pnl_pct <= -self.params['take_profit']:
                    engine.submit_order(
                        symbol='IF',
                        side=OrderSide.BUY,
                        quantity=abs(current_position),
                        order_type=OrderType.MARKET,
                        reason=f"空头止盈({pnl_pct*100:.2f}%<=-{self.params['take_profit']*100:.0f}%)"
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
                    order_type=OrderType.MARKET,
                    reason=f"均线金叉({self.params['fast_period']}/{self.params['slow_period']})，平空转多"
                )
                current_position = 0
            engine.submit_order(
                symbol='IF',
                side=OrderSide.BUY,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET,
                reason=f"均线金叉({self.params['fast_period']}/{self.params['slow_period']})，开多"
            )
            self.entry_price = current_price
            
        elif fast_ma < slow_ma and current_position >= 0:
            if current_position > 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.SELL,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET,
                    reason=f"均线死叉({self.params['fast_period']}/{self.params['slow_period']})，平多转空"
                )
                current_position = 0
            engine.submit_order(
                symbol='IF',
                side=OrderSide.SELL,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET,
                reason=f"均线死叉({self.params['fast_period']}/{self.params['slow_period']})，开空"
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
                    order_type=OrderType.MARKET,
                    reason=f"价格{current_price:.2f}跌破布林下轨{lower_band:.2f}，平空转多"
                )
                current_position = 0  # 更新本地持仓状态
            # 开多
            engine.submit_order(
                symbol='IF',
                side=OrderSide.BUY,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET,
                reason=f"价格{current_price:.2f}跌破布林下轨{lower_band:.2f}，开多"
            )
            
        elif current_price > upper_band and current_position >= 0:
            # 先平多，再开空
            if current_position > 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.SELL,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET,
                    reason=f"价格{current_price:.2f}突破布林上轨{upper_band:.2f}，平多转空"
                )
                current_position = 0  # 更新本地持仓状态
            # 开空
            engine.submit_order(
                symbol='IF',
                side=OrderSide.SELL,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET,
                reason=f"价格{current_price:.2f}突破布林上轨{upper_band:.2f}，开空"
            )
            
        # 回到中轨平仓
        elif abs(current_price - middle_band) / middle_band < 0.005 and current_position != 0:
            if current_position > 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.SELL,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET,
                    reason=f"价格{current_price:.2f}回归布林中轨{middle_band:.2f}，平多"
                )
            else:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.BUY,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET,
                    reason=f"价格{current_price:.2f}回归布林中轨{middle_band:.2f}，平空"
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
                    order_type=OrderType.MARKET,
                    reason=f"RSI={rsi:.1f}超卖(<{self.params['oversold']})，平空转多"
                )
                current_position = 0
            engine.submit_order(
                symbol='IF',
                side=OrderSide.BUY,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET,
                reason=f"RSI={rsi:.1f}超卖(<{self.params['oversold']})，开多"
            )
            
        elif rsi > self.params['overbought'] and current_position >= 0:
            if current_position > 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.SELL,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET,
                    reason=f"RSI={rsi:.1f}超买(>{self.params['overbought']})，平多转空"
                )
                current_position = 0
            engine.submit_order(
                symbol='IF',
                side=OrderSide.SELL,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET,
                reason=f"RSI={rsi:.1f}超买(>{self.params['overbought']})，开空"
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
                    order_type=OrderType.MARKET,
                    reason=f"价格{current_price:.2f}突破{self.params['lookback']}日高点{highest:.2f}，平空转多"
                )
                current_position = 0
            engine.submit_order(
                symbol='IF',
                side=OrderSide.BUY,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET,
                reason=f"价格{current_price:.2f}突破{self.params['lookback']}日高点{highest:.2f}，开多"
            )
            
        elif current_price < lowest and current_position >= 0:
            if current_position > 0:
                engine.submit_order(
                    symbol='IF',
                    side=OrderSide.SELL,
                    quantity=abs(current_position),
                    order_type=OrderType.MARKET,
                    reason=f"价格{current_price:.2f}跌破{self.params['lookback']}日低点{lowest:.2f}，平多转空"
                )
                current_position = 0
            engine.submit_order(
                symbol='IF',
                side=OrderSide.SELL,
                quantity=self.params['position_size'],
                order_type=OrderType.MARKET,
                reason=f"价格{current_price:.2f}跌破{self.params['lookback']}日低点{lowest:.2f}，开空"
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
                    order_type=OrderType.MARKET,
                    reason=f"空头止盈：最低价{bar_low:.2f}达开仓价{self.entry_price:.2f}的-{self.params['take_profit']*100:.0f}%"
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
                    order_type=OrderType.MARKET,
                    reason=f"空头止损：最高价{bar_high:.2f}达开仓价{self.entry_price:.2f}的+{self.params['stop_loss']*100:.0f}%"
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
                order_type=OrderType.MARKET,
                reason=f"隔日高开：前收{self.prev_close:.2f}+{self.params['entry_pct']*100:.0f}%触发价{entry_price:.2f}，开空"
            )
            self.entry_price = entry_price
            self.prev_close = current_price
            return
        
        # 无交易，更新收盘价
        self.prev_close = current_price


class FourDayFlipShortStrategy(Strategy):
    """
    4日翻转短线策略
    1. 连续4天阴线(当日收盘<当日开盘)且累计跌幅大于6%：下一交易日开盘开多仓
    2. 连续4天阳线(当日收盘>当日开盘)且累计涨幅大于6%：下一交易日开盘开空仓
    3. 盈利8%平仓
    4. 亏损达2%平仓
    说明：阴/阳线按K线实体(收盘vs开盘)判定，不比较前一日收盘；
          累计涨跌幅 = (当日收盘 / streak_days日前的收盘) - 1
    """

    def __init__(self, params: Dict = None):
        default_params = {
            'position_size': 1,
            'streak_days': 4,     # 连续阴/阳天数
            'threshold': 0.06,    # 累计涨跌幅阈值 6%
            'take_profit': 0.08,  # 止盈 8%
            'stop_loss': 0.02     # 止损 2%
        }
        if params:
            default_params.update(params)
        super().__init__(default_params)

        self.opens = []          # 历史开盘价
        self.closes = []         # 历史收盘价
        self.entry_price = None  # 开仓价
        self.pending = None      # 待执行方向: 'long'/'short'（下一开盘执行）
        self._execute_bar = False  # 是否已在开盘成交（防止同一根bar重复）

    def _get_position(self, engine):
        """从引擎获取当前持仓（正数=多头，负数=空头，0=空仓）"""
        if engine.portfolio.positions:
            pos = list(engine.portfolio.positions.values())[0]
            return pos.quantity if pos.side.value == 'long' else -pos.quantity
        return 0

    def _is_4day_setup(self, days=None):
        """判断最近streak_days根K线是否全阴/全阳(按实体)，返回 ('long'/'short'/None)
        long  : 连续阴线(收<开)且累计跌幅>阈值 → 开多
        short : 连续阳线(收>开)且累计涨幅>阈值 → 开空
        """
        streak = self.params['streak_days']
        threshold = self.params['threshold']
        n = len(self.closes)
        if n < streak + 1:
            return None
        # 最近 streak 根K线的实体方向：阴=收<开，阳=收>开
        recent_open = self.opens[-streak:]
        recent_close = self.closes[-streak:]
        bearish = all(c < o for o, c in zip(recent_open, recent_close))
        bullish = all(c > o for o, c in zip(recent_open, recent_close))
        # 累计涨跌幅：以 streak_days 日前收盘为基准至今日收盘
        cumulative = (self.closes[-1] / self.closes[-(streak + 1)]) - 1
        if bearish and cumulative <= -threshold:
            return 'long'
        if bullish and cumulative >= threshold:
            return 'short'
        return None

    def on_bar(self, engine: BacktestEngine, bar: Dict):
        current_price = bar['close']
        bar_open = bar['open']
        bar_high = bar['high']
        bar_low = bar['low']
        self.opens.append(bar_open)
        self.closes.append(current_price)

        current_position = self._get_position(engine)
        streak = self.params['streak_days']
        need_bars = streak + 1  # 需要足够历史判断连续走势

        # 若当前bar已经开盘成交过，则不再做其它判断（仅一笔/bar）
        if self._execute_bar:
            self._execute_bar = False
            return

        # 持仓中：检查止盈止损
        if current_position != 0 and self.entry_price is not None:
            if current_position > 0:  # 多头
                if bar_high >= self.entry_price * (1 + self.params['take_profit']):
                    engine.submit_order(
                        symbol='IF', side=OrderSide.SELL,
                        quantity=abs(current_position),
                        order_type=OrderType.MARKET,
                        reason=f"多头止盈：最高{bar_high:.2f}达开仓价{self.entry_price:.2f}的+{self.params['take_profit']*100:.0f}%"
                    )
                    self.entry_price = None
                    self.pending = None
                    return
                if bar_low <= self.entry_price * (1 - self.params['stop_loss']):
                    engine.submit_order(
                        symbol='IF', side=OrderSide.SELL,
                        quantity=abs(current_position),
                        order_type=OrderType.MARKET,
                        reason=f"多头止损：最低{bar_low:.2f}达开仓价{self.entry_price:.2f}的-{self.params['stop_loss']*100:.0f}%"
                    )
                    self.entry_price = None
                    self.pending = None
                    return
            else:  # 空头
                if bar_low <= self.entry_price * (1 - self.params['take_profit']):
                    engine.submit_order(
                        symbol='IF', side=OrderSide.BUY,
                        quantity=abs(current_position),
                        order_type=OrderType.MARKET,
                        reason=f"空头止盈：最低{bar_low:.2f}达开仓价{self.entry_price:.2f}的-{self.params['take_profit']*100:.0f}%"
                    )
                    self.entry_price = None
                    self.pending = None
                    return
                if bar_high >= self.entry_price * (1 + self.params['stop_loss']):
                    engine.submit_order(
                        symbol='IF', side=OrderSide.BUY,
                        quantity=abs(current_position),
                        order_type=OrderType.MARKET,
                        reason=f"空头止损：最高{bar_high:.2f}达开仓价{self.entry_price:.2f}的+{self.params['stop_loss']*100:.0f}%"
                    )
                    self.entry_price = None
                    self.pending = None
                    return

        # 无持仓时处理待执行的信号（下一交易日开盘价成交）
        if current_position == 0 and self.pending is not None:
            direction = self.pending
            self.pending = None
            if direction == 'long':
                order = engine.submit_order(
                    symbol='IF', side=OrderSide.BUY,
                    quantity=self.params['position_size'],
                    order_type=OrderType.MARKET,
                    reason="连续{}天阴线跌幅>{}%，次日开盘开多".format(
                        streak, f"{self.params['threshold']*100:.0f}%"),
                    use_open=True
                )
            else:
                order = engine.submit_order(
                    symbol='IF', side=OrderSide.SELL,
                    quantity=self.params['position_size'],
                    order_type=OrderType.MARKET,
                    reason="连续{}天阳线涨幅>{}%，次日开盘开空".format(
                        streak, f"{self.params['threshold']*100:.0f}%"),
                    use_open=True
                )
            self.entry_price = order.filled_price if order.status == 'filled' else bar['open']
            self._execute_bar = True
            return

        # 空仓且无待执行：检测信号，设置次日待执行
        if current_position == 0 and len(self.closes) >= need_bars:
            setup = self._is_4day_setup()
            if setup == 'long' or setup == 'short':
                self.pending = setup


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
        'four_day_flip': FourDayFlipShortStrategy,
    }
    
    if strategy_name not in strategies:
        raise ValueError(f"未知策略: {strategy_name}，可选策略: {list(strategies.keys())}")
    
    return strategies[strategy_name](params)

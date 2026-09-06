"""
回测引擎核心模块 - 股指期货回测框架
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import copy


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"  # 市价单
    LIMIT = "limit"    # 限价单


class PositionSide(Enum):
    """持仓方向"""
    LONG = "long"
    SHORT = "short"


@dataclass
class Order:
    """订单数据类"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: float
    timestamp: datetime
    status: str = "pending"  # pending, filled, cancelled
    filled_price: float = 0.0
    filled_quantity: int = 0
    commission: float = 0.0


@dataclass
class Position:
    """持仓数据类"""
    symbol: str
    side: PositionSide
    quantity: int
    avg_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class Trade:
    """成交记录"""
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: float
    quantity: int
    timestamp: datetime
    commission: float = 0.0
    action: str = ""  # 开多/开空/平多/平空


class Portfolio:
    """投资组合管理"""
    
    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        
    @property
    def total_equity(self) -> float:
        """总权益"""
        return self.cash + sum(pos.unrealized_pnl for pos in self.positions.values())
    
    @property
    def margin_used(self) -> float:
        """已用保证金"""
        margin = 0
        for pos in self.positions.values():
            # 股指期货保证金比例约12%
            margin += pos.quantity * pos.avg_price * 300 * 0.12  # 合约乘数300
        return margin
    
    @property
    def available_margin(self) -> float:
        """可用保证金"""
        return self.cash - self.margin_used
    
    def update_position(self, trade: Trade):
        """根据成交更新持仓"""
        symbol = trade.symbol
        
        if symbol in self.positions:
            pos = self.positions[symbol]
            
            # 判断是否为平仓操作
            is_close = (trade.side == OrderSide.SELL and pos.side == PositionSide.LONG) or \
                       (trade.side == OrderSide.BUY and pos.side == PositionSide.SHORT)
            
            if is_close:
                # 平仓：计算已实现盈亏
                if trade.side == OrderSide.SELL:
                    pnl = (trade.price - pos.avg_price) * trade.quantity * 300
                else:
                    pnl = (pos.avg_price - trade.price) * trade.quantity * 300
                pos.realized_pnl += pnl
                self.cash += pnl - trade.commission
                
                # 减少持仓数量
                pos.quantity -= trade.quantity
                
                # 如果持仓清零，删除该仓位
                if pos.quantity <= 0:
                    del self.positions[symbol]
            else:
                # 加仓：计算新的平均价格
                total_quantity = pos.quantity + trade.quantity
                if total_quantity > 0:
                    pos.avg_price = (pos.avg_price * pos.quantity + trade.price * trade.quantity) / total_quantity
                pos.quantity = total_quantity
                self.cash -= trade.commission
        else:
            # 新建仓位
            side = PositionSide.LONG if trade.side == OrderSide.BUY else PositionSide.SHORT
            self.positions[symbol] = Position(
                symbol=symbol,
                side=side,
                quantity=trade.quantity,
                avg_price=trade.price
            )
            self.cash -= trade.commission
    
    def record_equity(self, timestamp: datetime):
        """记录权益曲线"""
        self.equity_curve.append((timestamp, self.total_equity))
    
    def get_equity_df(self) -> pd.DataFrame:
        """获取权益曲线DataFrame"""
        if not self.equity_curve:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.equity_curve, columns=['date', 'equity'])
        df['returns'] = df['equity'].pct_change()
        df['cumulative_returns'] = (1 + df['returns']).cumprod() - 1
        return df


class BacktestEngine:
    """回测引擎主类"""
    
    def __init__(
        self,
        initial_capital: float = 1000000.0,
        commission_rate: float = 0.000023,  # 股指期货手续费率
        slippage: float = 0.2,  # 滑点（指数点）
        margin_ratio: float = 0.12,  # 保证金比例
        contract_multiplier: int = 300,  # 合约乘数
        max_trades_per_year: int = 24  # 每年最大开仓次数
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage
        self.margin_ratio = margin_ratio
        self.contract_multiplier = contract_multiplier
        self.max_trades_per_year = max_trades_per_year
        
        self.portfolio = Portfolio(initial_capital)
        self.data = None
        self.current_bar_index = 0
        self.current_timestamp = None
        
        # 年度交易计数
        self.year_trade_count = 0
        self.current_year = None
        
    def load_data(self, data: pd.DataFrame):
        """加载历史数据"""
        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_columns):
            raise ValueError(f"数据必须包含以下列: {required_columns}")
        
        self.data = data.sort_values('date').reset_index(drop=True)
        
    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: float = None,
        order_type: OrderType = OrderType.MARKET
    ) -> Order:
        """提交订单"""
        # 检查年度交易次数限制
        if self.current_timestamp is not None:
            trade_year = self.current_timestamp.year if hasattr(self.current_timestamp, 'year') else None
            if trade_year is not None:
                if trade_year != self.current_year:
                    self.current_year = trade_year
                    self.year_trade_count = 0
                
                # 检查是否达到年度限制（只计算开仓交易）
                pos = self.portfolio.positions.get(symbol)
                is_open = (pos is None) or \
                          (side == OrderSide.BUY and pos.side == PositionSide.SHORT) or \
                          (side == OrderSide.SELL and pos.side == PositionSide.LONG) or \
                          (pos is not None and side == OrderSide.BUY and pos.side == PositionSide.LONG and quantity > pos.quantity) or \
                          (pos is not None and side == OrderSide.SELL and pos.side == PositionSide.SHORT and quantity > pos.quantity)
                
                if is_open and self.year_trade_count >= self.max_trades_per_year:
                    return Order(
                        order_id=f"ORD_{len(self.portfolio.trades) + 1:06d}",
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        quantity=quantity,
                        price=price or self.get_current_price(),
                        timestamp=self.current_timestamp,
                        status="rejected"
                    )
        
        order = Order(
            order_id=f"ORD_{len(self.portfolio.trades) + 1:06d}",
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price or self.get_current_price(),
            timestamp=self.current_timestamp,
        )
        
        # 模拟成交
        if self.current_bar_index < len(self.data):
            fill_price = self.get_current_price()
            if order_type == OrderType.LIMIT:
                if side == OrderSide.BUY and price >= fill_price:
                    fill_price = price
                elif side == OrderSide.SELL and price <= fill_price:
                    fill_price = price
                else:
                    return order  # 未成交
            
            # 加入滑点
            if side == OrderSide.BUY:
                fill_price += self.slippage
            else:
                fill_price -= self.slippage
            
            # 判断开平仓动作
            action = ""
            pos = self.portfolio.positions.get(symbol)
            if side == OrderSide.BUY:
                if pos and pos.side == PositionSide.SHORT:
                    action = "平空"
                elif pos and pos.side == PositionSide.LONG:
                    action = "开多"
                else:
                    action = "开多"
            else:
                if pos and pos.side == PositionSide.LONG:
                    action = "平多"
                elif pos and pos.side == PositionSide.SHORT:
                    action = "开空"
                else:
                    action = "开空"
            
            # 计算手续费
            commission = fill_price * quantity * self.contract_multiplier * self.commission_rate
            
            # 创建成交记录
            trade = Trade(
                trade_id=f"TRD_{len(self.portfolio.trades) + 1:06d}",
                order_id=order.order_id,
                symbol=symbol,
                side=side,
                price=fill_price,
                quantity=quantity,
                timestamp=self.current_timestamp,
                commission=commission,
                action=action
            )
            
            # 更新组合
            self.portfolio.trades.append(trade)
            self.portfolio.update_position(trade)
            
            # 统计年度开仓次数
            if action in ["开多", "开空"]:
                self.year_trade_count += 1
            
            order.status = "filled"
            order.filled_price = fill_price
            order.filled_quantity = quantity
            order.commission = commission
        
        return order
    
    def get_current_price(self) -> float:
        """获取当前价格"""
        if self.data is not None and self.current_bar_index < len(self.data):
            return self.data.iloc[self.current_bar_index]['close']
        return 0.0
    
    def get_current_bar(self) -> Dict:
        """获取当前K线数据"""
        if self.data is not None and self.current_bar_index < len(self.data):
            return self.data.iloc[self.current_bar_index].to_dict()
        return {}
    
    def run(self, strategy, progress_callback=None):
        """
        运行回测
        
        Args:
            strategy: 策略实例，需实现on_bar方法
            progress_callback: 进度回调函数
        """
        if self.data is None or self.data.empty:
            raise ValueError("请先加载数据")
        
        total_bars = len(self.data)
        
        for i in range(total_bars):
            self.current_bar_index = i
            self.current_timestamp = self.data.iloc[i]['date']
            
            # 更新持仓未实现盈亏
            self._update_positions_pnl()
            
            # 记录权益
            self.portfolio.record_equity(self.current_timestamp)
            
            # 调用策略的on_bar方法
            strategy.on_bar(self, self.get_current_bar())
            
            # 进度回调
            if progress_callback and i % 100 == 0:
                progress_callback(i / total_bars * 100)
        
        return self.portfolio.get_equity_df()
    
    def _update_positions_pnl(self):
        """更新持仓未实现盈亏"""
        current_price = self.get_current_price()
        
        for symbol, pos in self.portfolio.positions.items():
            if pos.side == PositionSide.LONG:
                pos.unrealized_pnl = (current_price - pos.avg_price) * pos.quantity * self.contract_multiplier
            else:
                pos.unrealized_pnl = (pos.avg_price - current_price) * pos.quantity * self.contract_multiplier


class Strategy:
    """策略基类"""
    
    def __init__(self, params: Dict = None):
        self.params = params or {}
        
    def on_bar(self, engine: BacktestEngine, bar: Dict):
        """
        每根K线触发
        
        Args:
            engine: 回测引擎实例
            bar: 当前K线数据 {date, open, high, low, close, volume}
        """
        raise NotImplementedError
    
    def on_init(self, engine: BacktestEngine):
        """策略初始化"""
        pass
    
    def on_order(self, order: Order):
        """订单状态变化"""
        pass

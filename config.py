"""
配置文件 - 回测参数配置
"""
import os
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class BacktestConfig:
    """回测配置"""
    # 数据配置
    data_source: str = "akshare"  # 数据源: akshare/tushare/csv
    symbol: str = "IF0"        # 合约代码
    start_date: str = "2025-09-01"
    end_date: str = "2026-09-01"
    
    # 资金配置
    initial_capital: float = 1000000.0  # 初始资金
    margin_ratio: float = 0.12          # 保证金比例
    contract_multiplier: int = 300      # 合约乘数
    
    # 交易成本
    commission_rate: float = 0.000023   # 手续费率
    slippage: float = 0.2              # 滑点（指数点）
    
    # 策略配置
    strategy_name: str = "dual_ma"      # 策略名称
    strategy_params: Dict[str, Any] = None  # 策略参数
    
    # 输出配置
    output_dir: str = "output"
    save_trades: bool = True
    
    def __post_init__(self):
        if self.strategy_params is None:
            self.strategy_params = {}


@dataclass
class StrategyConfig:
    """策略参数配置"""
    
    # 双均线策略
    DUAL_MA = {
        'short_window': 5,
        'long_window': 20,
        'position_size': 1
    }
    
    # 均线交叉策略
    MA_CROSS = {
        'fast_period': 10,
        'slow_period': 30,
        'stop_loss': 0.02,
        'take_profit': 0.05,
        'position_size': 1
    }
    
    # 布林带策略
    BOLLINGER = {
        'window': 20,
        'num_std': 2.0,
        'position_size': 1
    }
    
    # RSI策略
    RSI = {
        'rsi_period': 14,
        'oversold': 30,
        'overbought': 70,
        'position_size': 1
    }
    
    # 动量突破策略
    MOMENTUM = {
        'lookback': 20,
        'position_size': 1
    }


# 默认配置
DEFAULT_CONFIG = BacktestConfig()


def load_config(config_file: str = None) -> BacktestConfig:
    """
    加载配置
    
    Args:
        config_file: 配置文件路径（JSON格式）
        
    Returns:
        BacktestConfig实例
    """
    import json
    
    config = BacktestConfig()
    
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    return config


def save_config(config: BacktestConfig, config_file: str):
    """保存配置到JSON文件"""
    import json
    
    data = {
        'data_source': config.data_source,
        'symbol': config.symbol,
        'start_date': config.start_date,
        'end_date': config.end_date,
        'initial_capital': config.initial_capital,
        'margin_ratio': config.margin_ratio,
        'contract_multiplier': config.contract_multiplier,
        'commission_rate': config.commission_rate,
        'slippage': config.slippage,
        'strategy_name': config.strategy_name,
        'strategy_params': config.strategy_params,
        'output_dir': config.output_dir,
    }
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

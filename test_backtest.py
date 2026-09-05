"""
测试脚本 - 验证回测系统功能
"""
import os
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sample_data import generate_sample_data
from config import BacktestConfig
from data_handler import CSVDataHandler
from engine import BacktestEngine
from strategies import get_strategy
from metrics import PerformanceAnalyzer
from visualization import Visualizer


def test_backtest():
    """测试回测流程"""
    print("="*60)
    print("          回测系统测试")
    print("="*60)
    
    # 1. 生成测试数据
    print("\n[1/5] 生成测试数据...")
    data = generate_sample_data(
        start_date="2023-01-01",
        end_date="2023-12-31",
        initial_price=4000.0
    )
    print(f"  生成 {len(data)} 条数据")
    
    # 2. 初始化引擎
    print("\n[2/5] 初始化回测引擎...")
    engine = BacktestEngine(
        initial_capital=1000000.0,
        commission_rate=0.000023,
        slippage=0.2
    )
    engine.load_data(data)
    
    # 3. 测试所有策略
    strategies = ['dual_ma', 'ma_cross', 'bollinger', 'rsi', 'momentum']
    
    for strategy_name in strategies:
        print(f"\n[3/5] 测试策略: {strategy_name}...")
        
        # 重新初始化引擎
        engine = BacktestEngine(
            initial_capital=1000000.0,
            commission_rate=0.000023,
            slippage=0.2
        )
        engine.load_data(data)
        
        # 加载策略
        strategy = get_strategy(strategy_name)
        
        # 运行回测
        equity_df = engine.run(strategy)
        
        # 计算绩效
        analyzer = PerformanceAnalyzer()
        metrics = analyzer.calculate_metrics(
            equity_df,
            engine.portfolio.trades,
            1000000.0
        )
        
        print(f"  总收益率: {metrics.total_return:.2%}")
        print(f"  夏普比率: {metrics.sharpe_ratio:.2f}")
        print(f"  最大回撤: {metrics.max_drawdown:.2%}")
        print(f"  交易次数: {metrics.total_trades}")
    
    # 4. 生成可视化报告
    print("\n[4/5] 生成可视化报告...")
    visualizer = Visualizer("test_output")
    
    # 使用双均线策略的结果
    engine = BacktestEngine(initial_capital=1000000.0)
    engine.load_data(data)
    strategy = get_strategy('dual_ma')
    equity_df = engine.run(strategy)
    
    charts = visualizer.generate_all_charts(
        equity_df,
        engine.portfolio.trades,
        prefix="test"
    )
    
    print(f"  图表已保存到: test_output/")
    
    # 5. 测试完成
    print("\n[5/5] 测试完成!")
    print("="*60)
    print("所有功能测试通过!")
    print("="*60)


if __name__ == "__main__":
    test_backtest()

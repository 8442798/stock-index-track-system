"""
股指期货回测系统 - 主程序入口
"""
import os
import sys
from datetime import datetime

from config import BacktestConfig, load_config, save_config, StrategyConfig
from data_handler import get_data_handler
from engine import BacktestEngine
from strategies import get_strategy
from metrics import PerformanceAnalyzer
from visualization import Visualizer


def run_backtest(config: BacktestConfig = None):
    """
    运行回测
    
    Args:
        config: 回测配置，如果为None则使用默认配置
    """
    if config is None:
        config = BacktestConfig()
    
    print("="*60)
    print("          股指期货回测系统")
    print("="*60)
    
    # 显示配置
    print("\n【回测配置】")
    print(f"  合约代码:      {config.symbol}")
    print(f"  回测周期:      {config.start_date} 至 {config.end_date}")
    print(f"  初始资金:      {config.initial_capital:,.2f} 元")
    print(f"  策略名称:      {config.strategy_name}")
    print(f"  策略参数:      {config.strategy_params}")
    
    # 1. 获取数据
    print("\n[1/4] 获取历史数据...")
    data_handler = get_data_handler(config.data_source)
    data = data_handler.get_futures_data(
        symbol=config.symbol,
        start_date=config.start_date,
        end_date=config.end_date
    )
    
    if data.empty:
        print("错误: 无法获取数据，请检查合约代码和日期范围")
        return None
    
    print(f"  获取到 {len(data)} 条数据")
    print(f"  时间范围: {data['date'].min()} 至 {data['date'].max()}")
    
    # 2. 初始化回测引擎
    print("\n[2/4] 初始化回测引擎...")
    engine = BacktestEngine(
        initial_capital=config.initial_capital,
        commission_rate=config.commission_rate,
        slippage=config.slippage,
        margin_ratio=config.margin_ratio,
        contract_multiplier=config.contract_multiplier
    )
    engine.load_data(data)
    
    # 3. 加载策略
    print("\n[3/4] 加载策略...")
    strategy = get_strategy(config.strategy_name, config.strategy_params)
    print(f"  策略: {config.strategy_name}")
    
    # 4. 运行回测
    print("\n[4/4] 运行回测...")
    
    def progress_callback(progress):
        print(f"\r  进度: {progress:.1f}%", end="", flush=True)
    
    equity_df = engine.run(strategy, progress_callback)
    print("\n  回测完成!")
    
    # 5. 计算绩效指标
    print("\n计算绩效指标...")
    analyzer = PerformanceAnalyzer()
    metrics = analyzer.calculate_metrics(
        equity_df,
        engine.portfolio.trades,
        config.initial_capital
    )
    analyzer.print_report(metrics)
    
    # 6. 生成可视化图表
    print("\n生成可视化图表...")
    visualizer = Visualizer(config.output_dir)
    charts = visualizer.generate_all_charts(
        equity_df,
        engine.portfolio.trades,
        prefix=config.strategy_name
    )
    print(f"  图表已保存到: {config.output_dir}/")
    
    # 7. 保存交易记录
    if config.save_trades and engine.portfolio.trades:
        trades_file = os.path.join(config.output_dir, f"{config.strategy_name}_trades.csv")
        trades_data = []
        
        # 配对交易计算盈亏
        open_positions = {}  # 持仓记录: symbol -> {price, side, quantity}
        
        for trade in engine.portfolio.trades:
            pnl_amount = None
            pnl_percent = None
            pnl_points = None
            
            symbol = trade.symbol
            
            if symbol in open_positions:
                pos = open_positions[symbol]
                
                # 判断是否为平仓操作
                is_close = (trade.side.value == 'sell' and pos['side'] == 'buy') or \
                           (trade.side.value == 'buy' and pos['side'] == 'sell')
                
                if is_close:
                    # 计算股指盈亏点数
                    if pos['side'] == 'buy':
                        pnl_points = trade.price - pos['price']
                    else:
                        pnl_points = pos['price'] - trade.price
                    
                    # 计算盈亏金额
                    pnl_amount = pnl_points * trade.quantity * config.contract_multiplier - trade.commission
                    
                    # 计算盈亏比例
                    cost = pos['price'] * trade.quantity * config.contract_multiplier
                    if cost > 0:
                        pnl_percent = (pnl_amount / cost) * 100
                    
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
            
            trades_data.append({
                'trade_id': trade.trade_id,
                'order_id': trade.order_id,
                'symbol': trade.symbol,
                'action': trade.action,
                'side': trade.side.value,
                'price': trade.price,
                'quantity': trade.quantity,
                'timestamp': trade.timestamp,
                'commission': trade.commission,
                'pnl_points': round(pnl_points, 2) if pnl_points is not None else '',
                'pnl_amount': round(pnl_amount, 2) if pnl_amount is not None else '',
                'pnl_percent': round(pnl_percent, 4) if pnl_percent is not None else ''
            })
        
        import pandas as pd
        pd.DataFrame(trades_data).to_csv(trades_file, index=False, encoding='utf-8-sig')
        print(f"  交易记录已保存: {trades_file}")
    
    print("\n" + "="*60)
    print("          回测完成")
    print("="*60)
    
    return {
        'equity_df': equity_df,
        'metrics': metrics,
        'trades': engine.portfolio.trades,
        'charts': charts
    }


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='股指期货回测系统')
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--symbol', type=str, help='合约代码，如 IF2401')
    parser.add_argument('--start', type=str, help='开始日期 YYYY-MM-DD')
    parser.add_argument('--end', type=str, help='结束日期 YYYY-MM-DD')
    parser.add_argument('--strategy', type=str, help='策略名称')
    parser.add_argument('--capital', type=float, help='初始资金')
    parser.add_argument('--list-strategies', action='store_true', help='列出可用策略')
    
    args = parser.parse_args()
    
    # 列出可用策略
    if args.list_strategies:
        print("可用策略:")
        print("  - dual_ma:    双均线策略")
        print("  - ma_cross:   均线交叉策略（支持止盈止损）")
        print("  - bollinger:  布林带策略")
        print("  - rsi:        RSI均值回归策略")
        print("  - momentum:   动量突破策略")
        return
    
    # 加载配置
    if args.config:
        config = load_config(args.config)
    else:
        config = BacktestConfig()
    
    # 命令行参数覆盖配置
    if args.symbol:
        config.symbol = args.symbol
    if args.start:
        config.start_date = args.start
    if args.end:
        config.end_date = args.end
    if args.strategy:
        config.strategy_name = args.strategy
    if args.capital:
        config.initial_capital = args.capital
    
    # 运行回测
    result = run_backtest(config)
    
    return result


if __name__ == "__main__":
    main()

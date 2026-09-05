"""
示例数据生成器 - 用于测试回测系统
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_sample_data(
    start_date: str = "2023-01-01",
    end_date: str = "2024-01-01",
    initial_price: float = 4000.0,
    volatility: float = 0.02
) -> pd.DataFrame:
    """
    生成模拟的股指期货数据
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        initial_price: 初始价格
        volatility: 波动率
        
    Returns:
        DataFrame with OHLCV data
    """
    # 生成日期序列（排除周末）
    dates = pd.bdate_range(start=start_date, end=end_date)
    
    # 生成价格数据（几何布朗运动）
    np.random.seed(42)
    n = len(dates)
    
    # 日收益率
    daily_returns = np.random.normal(0.0002, volatility, n)
    
    # 生成收盘价
    prices = initial_price * np.cumprod(1 + daily_returns)
    
    # 生成OHLCV数据
    data = []
    for i, date in enumerate(dates):
        close = prices[i]
        # 生成开高低收
        open_price = close * (1 + np.random.normal(0, 0.005))
        high = max(open_price, close) * (1 + abs(np.random.normal(0, 0.005)))
        low = min(open_price, close) * (1 - abs(np.random.normal(0, 0.005)))
        
        # 生成成交量
        volume = np.random.randint(50000, 200000)
        open_interest = np.random.randint(100000, 300000)
        
        data.append({
            'date': date,
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': volume,
            'open_interest': open_interest
        })
    
    return pd.DataFrame(data)


def save_sample_data(filename: str = "sample_data.csv", **kwargs):
    """保存示例数据到CSV文件"""
    df = generate_sample_data(**kwargs)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"示例数据已保存到: {filename}")
    print(f"数据条数: {len(df)}")
    print(f"时间范围: {df['date'].min()} 至 {df['date'].max()}")
    return df


if __name__ == "__main__":
    # 生成示例数据
    save_sample_data("data/sample_IF.csv")

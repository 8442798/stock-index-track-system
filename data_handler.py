"""
数据获取模块 - 支持AKShare和Tushare获取股指期货数据
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Union
import os


class DataHandler:
    """数据处理器基类"""
    
    def __init__(self):
        self.data = None
        
    def get_futures_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        freq: str = "daily"
    ) -> pd.DataFrame:
        """
        获取期货数据
        
        Args:
            symbol: 合约代码，如 'IF2401' (沪深300) 或 'IC2401' (中证500)
            start_date: 开始日期 'YYYY-MM-DD'
            end_date: 结束日期 'YYYY-MM-DD'
            freq: 数据频率 'daily'/'weekly'/'monthly'
            
        Returns:
            DataFrame with columns: [date, open, high, low, close, volume, open_interest]
        """
        raise NotImplementedError


class AKShareDataHandler(DataHandler):
    """使用AKShare获取数据"""
    
    def get_futures_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        freq: str = "daily"
    ) -> pd.DataFrame:
        try:
            import akshare as ak
            
            # 判断是否为主力合约
            if symbol.upper().endswith('0') or symbol.upper() == 'IF0':
                # 主力连续合约
                df = ak.futures_main_sina(
                    symbol=symbol,
                    start_date=start_date.replace('-', ''),
                    end_date=end_date.replace('-', '')
                )
                
                if df is None or df.empty:
                    return pd.DataFrame()
                
                # 标准化列名（中文列名）
                column_mapping = {
                    '日期': 'date',
                    '开盘价': 'open',
                    '最高价': 'high',
                    '最低价': 'low',
                    '收盘价': 'close',
                    '成交量': 'volume',
                    '持仓量': 'open_interest'
                }
                df = df.rename(columns=column_mapping)
                
            else:
                # 特定合约
                df = ak.futures_zh_daily_sina(symbol=symbol)
                
                if df is None or df.empty:
                    return pd.DataFrame()
                
                # 标准化列名
                df = df.rename(columns={
                    'date': 'date',
                    'open': 'open',
                    'high': 'high',
                    'low': 'low',
                    'close': 'close',
                    'volume': 'volume',
                    'hold': 'open_interest'
                })
            
            # 转换日期格式
            df['date'] = pd.to_datetime(df['date'])
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
            
            # 确保数值类型
            for col in ['open', 'high', 'low', 'close', 'volume', 'open_interest']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df[['date', 'open', 'high', 'low', 'close', 'volume', 'open_interest']].reset_index(drop=True)
            
        except Exception as e:
            print(f"AKShare获取数据失败: {e}")
            return pd.DataFrame()


class TushareDataHandler(DataHandler):
    """使用Tushare获取数据"""
    
    def __init__(self, token: str = None):
        super().__init__()
        self.token = token or os.environ.get('TUSHARE_TOKEN', '')
        
    def get_futures_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        freq: str = "daily"
    ) -> pd.DataFrame:
        try:
            import tushare as ts
            
            if not self.token:
                raise ValueError("请设置TUSHARE_TOKEN环境变量或传入token")
            
            pro = ts.pro_api(self.token)
            
            # 获取期货日线行情
            df = pro.fut_daily(
                ts_code=symbol,
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', '')
            )
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            # 标准化列名和格式
            df = df.rename(columns={
                'trade_date': 'date',
                'vol': 'volume',
                'oi': 'open_interest'
            })
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            return df[['date', 'open', 'high', 'low', 'close', 'volume', 'open_interest']]
            
        except Exception as e:
            print(f"Tushare获取数据失败: {e}")
            return pd.DataFrame()


class CSVDataHandler(DataHandler):
    """从CSV文件加载数据"""
    
    def __init__(self, data_dir: str = "data"):
        super().__init__()
        self.data_dir = data_dir
        
    def get_futures_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        freq: str = "daily"
    ) -> pd.DataFrame:
        try:
            file_path = os.path.join(self.data_dir, f"{symbol}.csv")
            
            if not os.path.exists(file_path):
                print(f"文件不存在: {file_path}")
                return pd.DataFrame()
            
            df = pd.read_csv(file_path)
            
            # 标准化列名
            column_mapping = {
                '日期': 'date',
                '开盘价': 'open',
                '最高价': 'high',
                '最低价': 'low',
                '收盘价': 'close',
                '成交量': 'volume',
                '持仓量': 'open_interest'
            }
            df = df.rename(columns=column_mapping)
            
            # 确保日期格式
            df['date'] = pd.to_datetime(df['date'])
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
            
            return df[['date', 'open', 'high', 'low', 'close', 'volume', 'open_interest']].reset_index(drop=True)
            
        except Exception as e:
            print(f"CSV加载数据失败: {e}")
            return pd.DataFrame()


def get_data_handler(source: str = "akshare", **kwargs) -> DataHandler:
    """
    工厂函数：根据数据源类型返回对应的数据处理器
    
    Args:
        source: 数据源类型 'akshare'/'tushare'/'csv'
        **kwargs: 传递给处理器的参数
        
    Returns:
        DataHandler实例
    """
    if source == "akshare":
        return AKShareDataHandler()
    elif source == "tushare":
        return TushareDataHandler(**kwargs)
    elif source == "csv":
        return CSVDataHandler(**kwargs)
    else:
        raise ValueError(f"不支持的数据源: {source}")

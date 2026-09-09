# -*- coding: utf-8 -*-
"""
Backtrader DataFeed adaptation for AKShare futures data.

Maps AKShare DataFrame format (date, open, high, low, close, volume, open_interest)
to backtrader's expected format.

Usage:
    from backtrader_datafeed import AkshareData
    import backtrader as bt
    import pandas as pd
    import akshare as ak

    # Fetch data
    df = ak.futures_daily(symbol="IF0", start_date="20240101", end_date="20241231")
    df = df[['date', 'open', 'high', 'low', 'close', 'volume', 'open_interest']]
    df['date'] = pd.to_datetime(df['date'])

    # Create data feed
    data = AkshareData(dataname=df)

    # Use with Cerebro
   cerebro = bt.Cerebro()
    cerebro.adddata(data)
</pandas>
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

import backtrader as bt
import pandas as pd


class AkshareData(bt.feeds.PandasData):
    """
    A backtrader DataFeed that reads from an AKShare-style DataFrame.

    Expected DataFrame columns (in order of backtrader params):
        - date   : datetime (can be index or a column)
        - open
        - high
        - low
        - close
        - volume
        - open_interest  (optional; if missing, defaults to 0)

    The `datetime` parameter should be set according to where the date column lives:
        - If `date` is the DataFrame index and is a DatetimeIndex: set `datetime=None`
        - If `date` is a column: set `datetime=-1` (or the column index) and list it in
          the data passed to `dataname` (PandasData will pick it up automatically when
          the column name matches the `open`/'high'/'low'/'close'/'volume'/'open_interest'
          params, but datetime needs explicit mapping if not the index).

    Typical use case: `date` is the index, so `datetime=None` and all column names
    match the default `PandasData` params.
    """

    params = (
        (
            "datetime",
            None,
        ),  # None means "use the DataFrame index if it's a DatetimeIndex"
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
        ("close", "close"),
        ("volume", "volume"),
        ("open_interest", "open_interest"),
        # The following are optional but often useful for broker calculations:
        ("openinterest", -1),  # -1 means "not provided"; set to 0 if you want to force 0
        ("time", -1),
        ("highf", -1),
        ("lowf", -1),
    )

    def __init__(self) -> None:
        # Ensure the base class wiring is correct.
        super().__init__()

    @classmethod
    def from_akshare_dataframe(
        cls,
        df: pd.DataFrame,
        *,
        datetime_col: Optional[str] = None,
        date_index: bool = True,
    ) -> AkshareData:
        """
        Factory that returns an AkshareData instance properly wired to a DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame with AKShare columns: date, open, high, low, close, volume,
            open_interest. The `date` column should ideally be the index (DatetimeIndex)
            or a column named exactly "date".
        datetime_col : str | None, optional
            If `date_index=False`, the name of the column containing datetime.
            Ignored if `date_index=True`.
        date_index : bool, default True
            If True (default), treat `df.index` as the datetime source and set
            `datetime=None` in the params. The caller should ensure the index is
            a DatetimeIndex.
            If False, `datetime` will be set to the column index/name per
            `datetime_col`.

        Returns
        -------
        AkshareData
            A backtrader DataFeed ready for `cerebro.adddata()`.
        """
        # Make a copy to avoid modifying the caller's DataFrame
        data_df = df.copy()

        if date_index:
            # Expect index to be DatetimeIndex
            if not isinstance(data_df.index, pd.DatetimeIndex):
                raise ValueError("When date_index=True, the DataFrame index must be a DatetimeIndex.")
            # Reset params: datetime=None means "use index"
            params = {
                "datetime": None,
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
                "open_interest": "open_interest",
            }
        else:
            if datetime_col is None or datetime_col not in data_df.columns:
                raise ValueError(
                    f"When date_index=False, provide a valid datetime column name. "
                    f"Got datetime_col={datetime_col}, columns={list(data_df.columns)}"
                )
            # We'll pass the DataFrame as-is and set datetime param to the column position
            # pandas backtrader feeds resolve column names when they match param names.
            # For explicit column-index mapping, we set datetime to -1 (first column) and
            # rely on the column order, or we can set it to the name if backtrader supports it.
            # Safer approach: set datetime to the column name if it's recognized.
            params = {
                "datetime": datetime_col,
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
                "open_interest": "open_interest",
            }

        # Instantiate the feed with the resolved params
        feed = cls(dataname=data_df, **params)
        return feed


def load_and_create_feed(
    symbol: str,
    start: str,
    end: str,
    *,
    date_index: bool = True,
) -> AkshareData:
    """
    Convenience function: fetch AKShare futures data and return an AkshareData feed.

    Parameters
    ----------
    symbol : str
        Futures symbol, e.g. "IF0", "IH0", "IC0", "IM0". The exchange is derived from
        the prefix: IF/IH -> CFFEX, IC/IM -> CZCE, etc.
    start : str
        Start date, format "YYYY-MM-DD" or "YYYYMMDD"
    end : str
        End date, format "YYYY-MM-DD" or "YYYYMMDD"
    date_index : bool, default True
        Whether the returned DataFrame should have a DatetimeIndex (True) or keep
        the date as a column (False).

    Returns
    -------
    AkshareData
        A backtrader DataFeed populated with the requested data.
    """
    import akshare as ak

    # Map symbol prefix to market
    market_map = {
        "IF": "CFFEX",
        "IH": "CFFEX",
        "IC": "CZCE",
        "IM": "CZCE",
    }
    prefix = symbol[:2]
    market = market_map.get(prefix, "CFFEX")  # default to CFFEX

    df = ak.get_futures_daily(start_date=start, end_date=end, market=market)

    # Standardize column names (AKShare may have slight variations)
    # Ensure we have the expected columns
    expected_cols = {"date", "open", "high", "low", "close", "volume", "open_interest"}
    having = set(df.columns)
    if not expected_cols.issubset(having):
        missing = expected_cols - having
        raise ValueError(
            f"AKShare data for {symbol} is missing columns: {missing}. "
            f"Got columns: {list(df.columns)}"
        )

    # Convert date column to datetime if it isn't already
    if date_index:
        df = df.set_index("date")
        # coerce to DatetimeIndex
        df.index = pd.to_datetime(df.index)
    else:
        df["date"] = pd.to_datetime(df["date"])

    return AkshareData.from_akshare_dataframe(df, date_index=date_index)


if __name__ == "__main__":
    # Quick smoke test
    import sys

    try:
        feed = load_and_create_feed("IF0", "20240901", "20240930", date_index=True)
        print("Feed created successfully.")
        print(f"Datetime type: {type(feed.datetime[0])}")
        print(f"Open value: {feed.open[0]}")
        print(f"Volume value: {feed.volume[0]}")
        print(f"Open interest value: {feed.open_interest[0]}")
    except Exception as e:
        print(f"Smoke test failed: {e}", file=sys.stderr)
        sys.exit(1)
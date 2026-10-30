"""Conventional OHLC-derived geometry, not validated Neely analysis."""
import numpy as np
import pandas as pd


def aggregate(d):
    d = d.sort_values('date').reset_index(drop=True)
    if d.empty or d.date.duplicated().any():
        raise ValueError('Empty input or duplicate dates')
    rows=[]
    for i in range(0,len(d),2):
        s=d.iloc[i:i+2]
        rows.append(dict(block=i//2+1,start_date=str(s.date.iloc[0].date()),
                         end_date=str(s.date.iloc[-1].date()),sessions=len(s),
                         open=float(s.open.iloc[0]),high=float(s.high.max()),
                         low=float(s.low.min()),close=float(s.close.iloc[-1]),
                         incomplete=len(s)<2))
    return pd.DataFrame(rows)

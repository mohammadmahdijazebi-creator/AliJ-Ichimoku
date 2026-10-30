"""Conventional OHLC-derived geometry, not validated Neely analysis."""
import numpy as np
import pandas as pd
from wave_review import swings


def cash_points(d, doji_order='LH'):
    """Two equal time slots per session, including flat sessions/duplicates.
    Keeping the raw slots is important: deleting equal prices must not shorten time.
    doji_order is a scenario, not known chronology.
    """
    if doji_order not in ('LH', 'HL'):
        raise ValueError('Invalid doji order')
    d = d.sort_values('date').reset_index(drop=True)
    if d.date.duplicated().any():
        raise ValueError('Duplicate sessions')
    ohlc = d[['open', 'high', 'low', 'close']].to_numpy(float)
    if not np.isfinite(ohlc).all() or (ohlc <= 0).any():
        raise ValueError('Invalid OHLC')
    if ((d.low > d[['open','close']].min(axis=1)) | (d.high < d[['open','close']].max(axis=1)) | (d.low>d.high)).any():
        raise ValueError('Inconsistent OHLC')
    rows=[]
    for day, r in enumerate(d.itertuples()):
        doji = r.close == r.open
        order = doji_order if doji else ('LH' if r.close > r.open else 'HL')
        for slot, kind in enumerate(order):
            rows.append(dict(idx=2*day+slot, session=day, date=str(r.date.date()),
                             price=float(r.low if kind=='L' else r.high), kind=kind,
                             assumed_order=order, doji=bool(doji),
                             order_known=bool(r.high==r.low)))
    return pd.DataFrame(rows)

def references(c):
    p=c.price.to_numpy(float)
    piv=swings(p,.08)
    rows=[]
    for k,pos in enumerate(range(max(0,len(piv)-3),len(piv)),1):
        i=piv[pos]
        prev=piv[pos-1] if pos else None
        rows.append(dict(id=f'P{k}',idx=i,date=c.date.iloc[i],price=p[i],
                         change_pct=None if prev is None else 100*(p[i]/p[prev]-1),
                         baseline_idx=prev,threshold_pct=8,
                         provisional=bool(pos==len(piv)-1)))
    return rows

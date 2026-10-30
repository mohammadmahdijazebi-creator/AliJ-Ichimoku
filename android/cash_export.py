"""Derived cash-data cache; raw candles remain authoritative in market.sqlite."""
import hashlib
import json
import os
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

VERSION = 'cash-v7-glyph-fallback-font17'
SUFFIXES = ('_cashdata.csv', '_cashdata.txt', '_pivots.csv', '_cashdata_wave.png',
            '_neowave.csv', '_neowave.png', '_cashdata_meta.json', '_wave_review_FA.png')

def sync_cash(store, sid, path, rows):
    db = store.db
    db.executescript('''CREATE TABLE IF NOT EXISTS cash_points(
        series INTEGER, idx INTEGER, stamp TEXT, price REAL, kind TEXT,
        PRIMARY KEY(series,idx));
        CREATE TABLE IF NOT EXISTS cash_exports(series INTEGER PRIMARY KEY, fingerprint TEXT);''')
    fingerprint = hashlib.sha256((VERSION + json.dumps(rows, ensure_ascii=False)).encode()).hexdigest()
    base = path.with_suffix('')
    symbol, source = db.execute('SELECT symbol,source FROM series WHERE id=?',(sid,)).fetchone()
    today = date.today().isoformat()
    destinations = {suffix:Path(str(base)+suffix) for suffix in SUFFIXES}
    for suffix, style in (('_cashdata_wave.png','cashdata_wave'),('_neowave.png','neowave'), ('_wave_review_FA.png','wave_review_FA')):
        folder = path.parent / source / style
        folder.mkdir(parents=True,exist_ok=True)
        destinations[suffix] = folder / f'{path.parent.name}_{today}.png'
    old = db.execute('SELECT fingerprint FROM cash_exports WHERE series=?', (sid,)).fetchone()
    if old and old[0] == fingerprint and all(p.exists() for p in destinations.values()):
        return
    import pandas as pd
    from cashdata import to_cash, zigzag, wave_chart, neowave_chart
    d = pd.DataFrame(rows, columns=['date','time','open','high','low','close','volume'])
    # Keep intraday timestamps; do not collapse candles sharing the same date.
    d['date'] = pd.to_datetime(d['date'] + ' ' + d['time'])
    c = to_cash(d); p = c.price.values; piv = zigzag(p, 25)
    with TemporaryDirectory(dir=path.parent) as tmp:
        staged = str(Path(tmp)/base.name)
        c.to_csv(staged+'_cashdata.csv', index=False)
        c.to_csv(staged+'_cashdata.txt', index=False, sep='\t')
        pd.DataFrame({'pivot_no':range(len(piv)), 'idx':piv,
                      'date':c.date.iloc[piv].values, 'price':p[piv]}).to_csv(staged+'_pivots.csv', index=False)
        waves = wave_chart(c, p, piv, base.name, staged, 700, '')
        # This second style intentionally aggregates to Jalali quarters, as in
        # the supplied script; the first chart always uses the selected timeframe.
        neowave_chart(d, base.name, staged, 40, 8)
        from wave_review import review_chart
        review_chart(d, symbol, source, staged+'_wave_review_FA.png')
        meta = {'version':VERSION, 'fingerprint':fingerprint, 'series':sid,
                'generated_date':today, 'symbol':symbol, 'source':source,
                'candles':len(rows), 'points':len(c), 'last_candle':str(d.date.iloc[-1]),
                'waves':waves, 'hl_order':'approximate: close>=open => L,H; otherwise H,L',
                'neowave_basis':'Jalali quarters aggregated from this series',
                'warning':'Wave zones are heuristic scenarios, not guaranteed forecasts.'}
        Path(staged+'_cashdata_meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        # Mark successful only after every file is published. Interrupted exports
        # are retried on the next synchronization, including corrected history.
        for suffix in SUFFIXES:
            os.replace(staged+suffix, destinations[suffix])
    with db:
        db.execute('DELETE FROM cash_points WHERE series=?',(sid,))
        db.executemany('INSERT INTO cash_points VALUES (?,?,?,?,?)',
                       [(sid,int(r.idx),str(r.date),float(r.price),r.type) for r in c.itertuples()])
        db.execute('INSERT OR REPLACE INTO cash_exports VALUES (?,?)',(sid,fingerprint))

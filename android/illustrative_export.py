"""Additive, source-isolated illustrative exports. Does not modify raw data."""
import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

VERSION = 'illustrative-1'

def sync_illustrative(store, sid, path, rows):
    symbol, source = store.db.execute('SELECT symbol,source FROM series WHERE id=?',(sid,)).fetchone()
    safe_source = re.sub(r'[^\w-]', '_', source)
    root = path.parent / safe_source / ('illustrative_'+str(sid))
    root.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256((VERSION+json.dumps(rows,ensure_ascii=False)).encode()).hexdigest()
    manifest = root/'latest.json'
    if manifest.exists():
        old = json.loads(manifest.read_text(encoding='utf-8'))
        if old.get('fingerprint') == fingerprint and all((root/p).is_file() for p in old.get('files',[])) and old.get('files'):
            return
    import pandas as pd
    from illustrative_chart import build
    d = pd.DataFrame(rows,columns=['date','time','open','high','low','close','volume'])
    d['date'] = pd.to_datetime(d['date'])
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S_%f')
    name = stamp+'_'+fingerprint[:10]
    with TemporaryDirectory(dir=root) as tmp:
        folder = Path(tmp)/name
        try:
            build(d,symbol,source,folder)
        except ValueError as exc:
            # Invalid daily input must not interrupt existing exports or imports.
            shutil.rmtree(folder,ignore_errors=True)
            folder.mkdir()
            (folder/'status.json').write_text(json.dumps(dict(symbol=symbol,source=source,status='not_generated',reason=str(exc)),ensure_ascii=False,indent=2),encoding='utf-8')
        d.to_csv(folder/'daily_source.csv',index=False,encoding='utf-8-sig')
        (folder/'README_FA.txt').write_text('طرح تقریبی هندسی، نه شمارش تأییدشدهٔ نئوویو.\nمبنای مسیر دو جلسهٔ معاملاتی و ترتیب قراردادی کف سپس سقف است.\nبرچسب W: حرکت هندسی با برگشت ۸ درصد. کانال: پوش رگرسیون لگاریتمی.\nپیوت سوم موقت است؛ فیبوناچی بر مبنای P3 + نسبت × (P2-P1) مشروط است.\nدر دادهٔ ناکافی هدفی تولید نمی‌شود. فایل daily_source.csv دادهٔ همین منبع است.\n',encoding='utf-8')
        archive = Path(shutil.make_archive(str(Path(tmp)/name),'zip',folder))
        files = [str(Path(name)/p.name) for p in folder.iterdir()]+[name+'.zip']
        os.replace(folder,root/name)
        os.replace(archive,root/(name+'.zip'))
        temp = root/'latest.tmp'
        temp.write_text(json.dumps(dict(version=VERSION,symbol=symbol,source=source,fingerprint=fingerprint,files=files),ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temp,manifest)

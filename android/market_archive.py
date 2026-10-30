"""Independent daily archive and cached, unshifted Ichimoku crossings."""
import csv, hashlib, json, math, os, sqlite3
from pathlib import Path
from collections import deque

PAIRS={'main':(26,52),'sub':(9,26)}

def midpoint(rows,period):
 hi,lo=deque(),deque();out=[]
 for i,r in enumerate(rows):
  while hi and rows[hi[-1]][3]<=r[3]:hi.pop()
  while lo and rows[lo[-1]][4]>=r[4]:lo.pop()
  hi.append(i);lo.append(i)
  while hi[0]<=i-period:hi.popleft()
  while lo[0]<=i-period:lo.popleft()
  out.append((rows[hi[0]][3]+rows[lo[0]][4])/2 if i>=period-1 else None)
 return out

def crossings(rows,kind):
 a,b=(midpoint(rows,p) for p in PAIRS[kind]);previous=0;events=[]
 for i,(x,y) in enumerate(zip(a,b)):
  if x is None or y is None:continue
  sign=(x>y)-(x<y)
  # Touching/equality is not a cross. Carry the last strictly nonzero side.
  if sign:
   if previous and previous!=sign:events.append((i,rows[i][0],sign,x,y))
   previous=sign
 return events

def atomic(path,text):
 path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
 tmp.write_text(text,encoding='utf-8');os.replace(tmp,path)

def connect(folder):
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
 db=sqlite3.connect(folder/'archive.sqlite',timeout=30)
 db.execute('PRAGMA journal_mode=WAL')
 db.executescript('''CREATE TABLE IF NOT EXISTS candles(symbol TEXT,date TEXT,time TEXT,o REAL,h REAL,l REAL,c REAL,v REAL,PRIMARY KEY(symbol,date,time));
 CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY,digest TEXT,events TEXT);
 CREATE TABLE IF NOT EXISTS downloads(symbol TEXT PRIMARY KEY,status TEXT,detail TEXT,updated TEXT);''')
 return db

def save_history(db,folder,symbol,rows):
 clean=[]
 for r in rows:
  if len(r)!=7 or not all(math.isfinite(float(v)) for v in r[2:]):raise ValueError('invalid OHLCV')
  if min(r[2:6])<=0 or r[3]<max(r[2],r[4],r[5]) or r[4]>min(r[2],r[5]):raise ValueError('invalid OHLC')
  clean.append(r)
 if not clean:raise ValueError('empty history')
 with db:db.executemany('INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?)',[(symbol,*r) for r in clean])
 rows=[list(r) for r in db.execute('SELECT date,time,o,h,l,c,v FROM candles WHERE symbol=? ORDER BY date,time',(symbol,))]
 name=hashlib.sha256(symbol.encode()).hexdigest()[:20]
 folder=Path(folder)
 atomic(folder/(name+'.json'),json.dumps({'symbol':symbol,'tf':1440,'source':'finpy','rows':rows},ensure_ascii=False))
 target=folder/(name+'.csv');tmp=target.with_suffix('.csv.tmp')
 with tmp.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['symbol','date','time','open','high','low','close','volume']);w.writerows([[symbol,*r] for r in rows])
 os.replace(tmp,target)
 return len(rows)

def search(folder,kind,last_n=None,start=None,end=None,notify=lambda s:None):
 folder=Path(folder);archive=folder/'all_market';db=connect(archive);results=[]
 try:
  def scan(symbol,source,rows,key):
   if not rows:return
   digest=hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest()
   hit=db.execute('SELECT digest,events FROM cache WHERE key=?',(key+kind,)).fetchone()
   if hit and hit[0]==digest:events=json.loads(hit[1])
   else:
    events=crossings(rows,kind)
    with db:db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',(key+kind,digest,json.dumps(events)))
   for i,date,direction,a,b in events:
    if last_n is not None and i<len(rows)-last_n:continue
    if start and date<start:continue
    if end and date>end:continue
    results.append((symbol,date,'صعودی' if direction>0 else 'نزولی',source,a,b,rows[-1][0]))
  for (symbol,) in db.execute('SELECT DISTINCT symbol FROM candles').fetchall():
   notify(symbol)
   rows=[list(r) for r in db.execute('SELECT date,time,o,h,l,c,v FROM candles WHERE symbol=? ORDER BY date,time',(symbol,))]
   scan(symbol,'آرشیو finpy',rows,'archive:'+symbol)
  bank=folder/'market.sqlite'
  if bank.exists():
   original=sqlite3.connect(bank.as_uri()+'?mode=ro',uri=True,timeout=30)
   try:
    for sid,symbol,source in original.execute('SELECT id,symbol,source FROM series WHERE tf=1440').fetchall():
     notify(symbol)
     rows=[list(r) for r in original.execute('SELECT date,time,o,h,l,c,v FROM candles WHERE series=? ORDER BY date,time',(sid,))]
     scan(symbol,'بانک / '+source,rows,'bank:'+str(sid))
   finally:original.close()
  return sorted(results,key=lambda r:(r[1],r[0]),reverse=True)
 finally:db.close()


def recent_search(folder,kind,last_n=5,notify=lambda s:None):
 """One freshest daily series per symbol; latest cross in its last N sessions.
 Ties prefer local finpy, then local file, then archive. Never merge OHLC.
 """
 if not 1<=last_n<=5:raise ValueError('تعداد روز باید بین ۱ و ۵ باشد')
 folder=Path(folder).resolve();db=connect(folder/'all_market');chosen={}
 def offer(symbol,rows,priority):
  if not rows:return
  symbol=symbol.replace('ي','ی').replace('ك','ک').replace('\u200c','').strip()
  rank=(rows[-1][0],priority,len(rows))
  if symbol not in chosen or rank>chosen[symbol][0]:chosen[symbol]=(rank,rows)
 try:
  for (symbol,) in db.execute('SELECT DISTINCT symbol FROM candles').fetchall():
   notify(symbol)
   offer(symbol,[list(r) for r in db.execute('SELECT date,time,o,h,l,c,v FROM candles WHERE symbol=? ORDER BY date,time',(symbol,))],0)
 finally:db.close()
 bank=folder/'market.sqlite'
 if bank.exists():
  db=sqlite3.connect(bank.as_uri()+'?mode=ro',uri=True)
  try:
   for sid,symbol,source in db.execute('SELECT id,symbol,source FROM series WHERE tf=1440').fetchall():
    notify(symbol)
    offer(symbol,[list(r) for r in db.execute('SELECT date,time,o,h,l,c,v FROM candles WHERE series=? ORDER BY date,time',(sid,))],2 if source=='finpy' else 1)
  finally:db.close()
 result=[]
 for symbol,(_,rows) in chosen.items():
  notify(symbol)
  events=crossings(rows,kind)
  if events and events[-1][0]>=len(rows)-last_n:
   _,date,direction,_,_=events[-1]
   result.append((symbol,date,'صعودی' if direction>0 else 'نزولی'))
 return sorted(result,key=lambda r:(r[1],r[0]),reverse=True)

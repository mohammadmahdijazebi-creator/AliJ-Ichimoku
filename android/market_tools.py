"""Independent daily market archive and unshifted cross scanner."""
import csv,json,hashlib,os,subprocess,sys,tempfile,time,sqlite3
from pathlib import Path
from datetime import date
from collections import deque

def atomic_json(path,data):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,path)

def midpoints(rows,p):
 hi,lo=deque(),deque();out=[]
 for i,r in enumerate(rows):
  while hi and rows[hi[-1]][3]<=r[3]:hi.pop()
  while lo and rows[lo[-1]][4]>=r[4]:lo.pop()
  hi.append(i);lo.append(i)
  while hi[0]<=i-p:hi.popleft()
  while lo[0]<=i-p:lo.popleft()
  out.append((rows[hi[0]][3]+rows[lo[0]][4])/2 if i>=p-1 else None)
 return out

def crossings(rows,p,q,sessions=5,start='',end=''):
 rows=sorted(rows,key=lambda r:(r[0],r[1]));a=midpoints(rows,p);b=midpoints(rows,q)
 previous=None;events=[]
 for i,(x,y) in enumerate(zip(a,b)):
  if x is None or y is None:continue
  sign=(x>y)-(x<y)
  if sign==0:continue # equality alone is not a cross; retain last strict side
  if previous is not None and sign!=previous:
   if (not sessions or i>=len(rows)-sessions) and (not start or rows[i][0]>=start) and (not end or rows[i][0]<=end):
    events.append({'date':rows[i][0],'direction':'صعودی' if sign>0 else 'نزولی','first':x,'second':y,'last':rows[-1][0]})
  previous=sign
 return events

def worker(mode,target,symbol='',stop=None):
 cmd=[sys.executable,str(Path(__file__).with_name('market_worker.py')),mode,str(target),symbol]
 with tempfile.TemporaryFile() as log:
  proc=subprocess.Popen(cmd,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  deadline=time.monotonic()+(240 if mode=='list' else 150)
  while proc.poll() is None:
   if (stop and stop.is_set()) or time.monotonic()>deadline:
    proc.kill();proc.wait()
    raise RuntimeError('متوقف شد' if stop and stop.is_set() else 'پایان مهلت اتصال')
   time.sleep(.2)
  if proc.returncode:
   log.seek(0);raise RuntimeError(log.read().decode('utf-8',errors='replace')[-1200:])
 return json.loads(target.read_text(encoding='utf-8'))

def download(folder,stop,progress):
 folder=Path(folder)/'market_archive';folder.mkdir(exist_ok=True)
 manifest=folder/'manifest.json'
 state=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {'items':{},'warnings':[]}
 with tempfile.TemporaryDirectory() as temp:
  target=Path(temp)/'result.json'
  progress('دریافت فهرست بازار و صندوق‌ها…')
  try:
   universe=worker('list',target,stop=stop)
   state['warnings']=universe['warnings'];state['symbols']=universe['symbols']
  except Exception as e:
   if stop.is_set():return 'دریافت متوقف شد.'
   if not state.get('symbols'):raise
   state['warnings']=[str(e),'از فهرست ذخیره‌شده استفاده شد.']
  atomic_json(manifest,state)
  symbols=state['symbols'];today=date.today().isoformat()
  for index,symbol in enumerate(symbols,1):
   if stop.is_set():break
   key=hashlib.sha256(symbol.encode()).hexdigest()[:24]
   old=state['items'].get(symbol,{})
   if old.get('updated')==today and old.get('status')=='ok' and (folder/(key+'.json')).exists() and (folder/(key+'.csv')).exists():continue
   progress(f'{index}/{len(symbols)} — {symbol}')
   try:
    rows=worker('history',target,symbol,stop)
    tmp=folder/(key+'.csv.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
     w=csv.writer(f);w.writerow(['date','time','open','high','low','close','volume']);w.writerows(rows)
    os.replace(tmp,folder/(key+'.csv'))
    atomic_json(folder/(key+'.json'),{'symbol':symbol,'source':'finpy','tf':1440,'rows':rows})
    state['items'][symbol]={'status':'ok','updated':today,'file':key,'count':len(rows)}
   except Exception as e:
    if stop.is_set():break
    state['items'][symbol]={**old,'status':'failed','error':str(e)}
   atomic_json(manifest,state)
   stop.wait(.3)
  ok=sum(v.get('status')=='ok' for v in state['items'].values())
  failed=sum(v.get('status')=='failed' for v in state['items'].values())
  return f'ذخیره موفق: {ok} | ناموفق: {failed} | فهرست: {len(symbols)}\n'+('متوقف شد؛ اجرای مجدد ادامه می‌دهد.\n' if stop.is_set() else '')+'پوشش همهٔ نمادهای تاریخی تضمین نمی‌شود؛ گزارش: market_archive/manifest.json\n'+'\n'.join(state['warnings'])

def scan(folder,p,q,sessions,start,end):
 results=[];errors=[];folder=Path(folder)
 def add(symbol,source,rows):
  for event in crossings(rows,p,q,sessions,start,end):results.append({'symbol':symbol,'source':source,**event})
 db=folder/'market.sqlite'
 if db.exists():
  con=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)
  try:
   for sid,symbol,source in con.execute('SELECT id,symbol,source FROM series WHERE tf=1440'):
    rows=con.execute('SELECT date,time,o,h,l,c,v FROM candles WHERE series=? ORDER BY date,time',(sid,)).fetchall()
    add(symbol,'بانک / '+source,rows)
  finally:con.close()
 for path in (folder/'market_archive').glob('*.json'):
  if path.name=='manifest.json':continue
  try:
   data=json.loads(path.read_text(encoding='utf-8'));add(data['symbol'],'آرشیو finpy',data['rows'])
  except Exception as e:errors.append(path.name+': '+str(e))
 results.sort(key=lambda r:(r['date'],r['symbol']),reverse=True)
 return results,errors

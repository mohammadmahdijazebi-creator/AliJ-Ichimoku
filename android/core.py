import csv, io, json, math, re, sqlite3, zipfile, os
from pathlib import Path
from datetime import datetime
from collections import Counter

KNOWN={'IRT1AHRM0001':'اهرم','IRO1IKCO0001':'خودرو'}
HEAD=['date','time','open','high','low','close','volume']
def normalize(s):
 return str(s).strip().replace('ي','ی').replace('ك','ک')
def decode(b):
 for enc in ('utf-8-sig','utf-16','cp1256'):
  try:return b.decode(enc)
  except UnicodeError:pass
 raise ValueError('کدگذاری فایل قابل خواندن نیست')
def date_value(s):
 s=str(s).strip().replace('/','-').replace('.','-')
 if re.fullmatch(r'\d{8}',s):s=f'{s[:4]}-{s[4:6]}-{s[6:]}'
 if int(s[:4])<1700:
  import jdatetime
  y,m,d=map(int,s.split('-'));return jdatetime.date(y,m,d).togregorian().isoformat()
 return datetime.strptime(s,'%Y-%m-%d').date().isoformat()
def parse_text(text):
 lines=[l for l in text.splitlines() if l.strip() and not l.lstrip().startswith('#')]
 if not lines:return []
 sample='\n'.join(lines[:10])
 try:sep=csv.Sniffer().sniff(sample,delimiters=',;\t').delimiter
 except csv.Error:sep=','
 rows=list(csv.reader(lines,delimiter=sep))
 aliases={'dtyyyymmdd':'date','تاریخ':'date','زمان':'time','ticker':'symbol','نماد':'symbol','per':'tf','period':'tf','تایم':'tf','vol':'volume','حجم':'volume'}
 header=[aliases.get(c.strip().lower().strip('<>'),c.strip().lower().strip('<>')) for c in rows[0]]
 has_header='date' in header
 if has_header and not {'open','high','low','close'}.issubset(header):raise ValueError('ستون‌های Open/High/Low/Close لازم است')
 out=[]
 for idx,r in enumerate(rows[1:] if has_header else rows,2 if has_header else 1):
  try:
   d=dict(zip(header if has_header else HEAD,r))
   day=date_value(d['date']);tm=d.get('time','00:00').strip()
   if tm in ('روزانه','daily','D',''):tm='00:00'
   if re.fullmatch(r'\d{4,6}',tm):tm=tm.zfill(6) if len(tm)==6 else tm;tm=tm[:2]+':'+tm[2:4]
   tm=datetime.strptime(tm[:5],'%H:%M').strftime('%H:%M')
   vals=[float(d[k]) for k in HEAD[2:6]]+[float(d.get('volume') or 0)]
   if not all(math.isfinite(v) for v in vals):raise ValueError('عدد نامعتبر')
   if any(v<=0 for v in vals[:4]):continue
   if vals[1]<max(vals[0],vals[2],vals[3]) or vals[2]>min(vals[0],vals[3]):raise ValueError('High/Low نامعتبر')
   out.append({'row':[day,tm,*vals],'symbol':normalize(d.get('symbol','')),'tf':d.get('tf','')})
  except Exception as e:raise ValueError(f'خط {idx}: {e}') from e
 return out

def inspect_file(path):
 """Never trust the outer ZIP name. Header/README identity; cadence from candles."""
 members=[];mapping=dict(KNOWN)
 if zipfile.is_zipfile(path):
  with zipfile.ZipFile(path) as z:
   if sum(i.file_size for i in z.infolist())>200_000_000:raise ValueError('حجم بازشده بیش از ۲۰۰ مگابایت است')
   for n in z.namelist():
    if Path(n).name.lower().startswith('readme'):
     for code,name in re.findall(r'(IR\w+)\s*:\s*([^\n\r]+)',decode(z.read(n))):mapping[code]=normalize(name)
   members=[(n,decode(z.read(n))) for n in z.namelist() if n.lower().endswith(('.csv','.txt')) and not Path(n).name.lower().startswith('readme')]
 else:members=[(Path(path).name,decode(Path(path).read_bytes()))]
 batches=[]
 for name,text in members:
  records=parse_text(text)
  if not records:continue
  groups={}
  for rec in records:groups.setdefault((rec['symbol'],rec['tf']),[]).append(rec['row'])
  for (sym,tf),rows in groups.items():
   # An internal instrument code is used only when mapped by metadata/known identity.
   if not sym:
    codes=[c for c in mapping if c in name]
    sym=mapping[codes[0]] if len(codes)==1 else ''
   sym=mapping.get(sym,sym)
   if str(tf).lower() in ('d','daily','روزانه'):tf=1440
   elif tf:tf=int(tf)
   else:
    times=sorted(set((r[0],r[1]) for r in rows))
    gaps=[int((datetime.fromisoformat(b[0]+'T'+b[1])-datetime.fromisoformat(a[0]+'T'+a[1])).total_seconds()/60) for a,b in zip(times,times[1:]) if a[0]==b[0]]
    tf=Counter(gaps).most_common(1)[0][0] if gaps else (1440 if len(times)>1 else 0)
   batches.append({'name':name,'symbol':sym,'tf':tf,'source':'file','rows':rows})
 if not batches:raise ValueError('هیچ کندل معتبری پیدا نشد')
 return batches

def analyze(rows):
 n=len(rows);high=[r[3] for r in rows];low=[r[4] for r in rows];vals={};trends={};effective={}
 for p in (9,26,52):
  a=[]
  for i in range(n+51):
   h=high[max(0,i-p+1):min(n,i+1)];l=low[max(0,i-p+1):min(n,i+1)]
   a.append((max(h)+min(l))/2 if i>=p-1 and h else None)
  vals[p]=a;trends[p]=[None]+[None if a[i] is None or a[i-1] is None else (a[i]>a[i-1])-(a[i]<a[i-1]) for i in range(1,len(a))]
  last=None;effective[p]=[]
  for d in trends[p]:
   if d not in (None,0):last=d
   effective[p].append(last if d is not None else None)
 def state(i,ref,other):
  a,b=effective[ref][i],effective[other][i]
  return None if a is None or b is None else ('همگرایی' if a==b else 'واگرایی')+' '+('صعودی' if a>0 else 'نزولی')
 def result(ref,other):
  current=state(n-1,ref,other);runs=[];count=1
  for i in range(n,n+51):
   st=state(i,ref,other)
   if st!=current:
    runs.append((current,count));current=st;count=0
    if len(runs)==2 or st is None:break
   count+=1
  else:
   if current is not None:runs.append((current,count))
  if len(runs)<2 and current is not None and count and (not runs or runs[-1]!=(current,count)):runs.append((current,count))
  labels=[];start=n-1
  for st,c in runs[:2]:
   parts=[]
   for d in trends[ref][start:start+c]:
    if parts and parts[-1][0]==d:parts[-1][1]+=1
    else:parts.append([d,1])
   detail=' ـ '.join(str(k)+' تا '+{0:'فلت',1:'صعودی',-1:'نزولی',None:'نامشخص'}[d] for d,k in parts)
   labels.append(st+' '+str(c)+' تا\n'+detail if st else 'داده کافی نیست');start+=c
  return labels+['داده کافی نیست']*(2-len(labels))
 main=result(26,52);sub=result(9,26)
 return {'signals':[main[0],sub[0],main[1],sub[1]],'values':[vals[p][n-1] for p in (52,26,9)],'last':' '.join(rows[-1][:2]),'count':n},vals

class Store:
 def __init__(self,folder):
  self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
  self.db=sqlite3.connect(self.folder/'market.sqlite',timeout=30)
  self.db.execute('PRAGMA journal_mode=WAL')
  self.db.executescript('''CREATE TABLE IF NOT EXISTS symbols(name TEXT PRIMARY KEY,position INTEGER);
  CREATE TABLE IF NOT EXISTS series(id INTEGER PRIMARY KEY,symbol TEXT,tf INTEGER,source TEXT,visible INTEGER DEFAULT 1,summary TEXT,UNIQUE(symbol,tf,source));
  CREATE TABLE IF NOT EXISTS candles(series INTEGER,date TEXT,time TEXT,o REAL,h REAL,l REAL,c REAL,v REAL,PRIMARY KEY(series,date,time));''')
 def close(self):self.db.close()
 def rows(self,sid):return [list(r) for r in self.db.execute('SELECT date,time,o,h,l,c,v FROM candles WHERE series=? ORDER BY date,time',(sid,))]
 def import_batches(self,batches):
  changed={};added=updated=0
  with self.db:
   for b in batches:
    sym=normalize(b['symbol']);tf=int(b['tf'])
    if not sym or tf<=0:raise ValueError('نماد و تایم معتبر الزامی است')
    pos=self.db.execute('SELECT COALESCE(MAX(position),0)+1 FROM symbols').fetchone()[0]
    self.db.execute('INSERT OR IGNORE INTO symbols VALUES (?,?)',(sym,0 if sym=='اهرم' else pos))
    self.db.execute('INSERT OR IGNORE INTO series(symbol,tf,source) VALUES (?,?,?)',(sym,tf,b['source']))
    sid=self.db.execute('SELECT id FROM series WHERE symbol=? AND tf=? AND source=?',(sym,tf,b['source'])).fetchone()[0]
    self.db.execute('UPDATE series SET visible=1 WHERE id=?',(sid,))
    for r in b['rows']:
     old=self.db.execute('SELECT o,h,l,c,v FROM candles WHERE series=? AND date=? AND time=?',(sid,*r[:2])).fetchone()
     if old is None or list(old)!=r[2:]:
      added+=old is None;updated+=old is not None
      self.db.execute('INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?)',(sid,*r))
      changed[sid]=min(changed.get(sid,tuple(r[:2])),tuple(r[:2]))
    if sid not in changed and not self.db.execute('SELECT summary FROM series WHERE id=?',(sid,)).fetchone()[0]:changed[sid]=('', '')
   for sid in changed:
    summary,_=analyze(self.rows(sid));summary['updated_at']=datetime.now().strftime('%Y-%m-%d %H:%M');self.db.execute('UPDATE series SET summary=? WHERE id=?',(json.dumps(summary,ensure_ascii=False),sid))
  # The database is authoritative. Exports are recoverable after an interruption.
  self.sync_exports()
  return added,updated
 def sync_exports(self):
  out=self.folder/'outputs';out.mkdir(exist_ok=True)
  for sid,sym,tf,source in self.db.execute('SELECT id,symbol,tf,source FROM series'):
   rows=self.rows(sid)
   if not rows:continue
   safe=re.sub(r'[^\w-]','_',sym)
   symbol_out=out/safe;symbol_out.mkdir(exist_ok=True)
   path=symbol_out/f'{sid}_{safe}_{tf}_{source}.csv'
   old=[]
   if path.exists():
    with path.open(encoding='utf-8-sig',newline='') as f:
     reader=csv.reader(f);next(reader,None)
     old=list(reader)
   summary,vals=analyze(rows)
   xlsx=path.with_suffix('.xlsx')
   header=HEAD+['tenkan_9','kijun_26','span_b_52']
   new=[[str(v) for v in r]+['' if vals[p][i] is None else str(vals[p][i]) for p in (9,26,52)] for i,r in enumerate(rows)]
   if old!=new or not xlsx.exists():
    self.export_excel(xlsx,sym,tf,source,rows,vals,summary)
   if tf==1440:
    from cash_export import sync_cash
    sync_cash(self,sid,path,rows)
    from illustrative_export import sync_illustrative
    sync_illustrative(self,sid,path,rows)
   if old==new:continue
   if path.exists() and new[:len(old)]==old:
    with path.open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerows(new[len(old):])
   else:
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
     w=csv.writer(f);w.writerow(header);w.writerows(new)
    os.replace(tmp,path)
  snapshot=self.list_series();target=out/'summary.json';tmp=target.with_suffix('.tmp')
  tmp.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,target)
 def export_excel(self,path,symbol,tf,source,rows,vals,summary):
  from openpyxl import Workbook
  from openpyxl.styles import Font, PatternFill, Alignment
  from openpyxl.utils import get_column_letter
  wb=Workbook();ws=wb.active;ws.title='داده و ایچیموکو'
  ws.append(['تاریخ','زمان','باز','بیشترین','کمترین','بسته','حجم','تنکان ۹','کیجون ۲۶','اسپن B ۵۲','روند تنکان','روند کیجون','روند اسپن B'])
  colors={'صعودی':'008000','نزولی':'FF0000','فلت':'FF9900'}
  for i,row in enumerate(rows):
   values=[vals[p][i] for p in (9,26,52)];trends=[]
   for p,v in zip((9,26,52),values):
    prev=vals[p][i-1] if i else None
    trends.append('نامشخص' if v is None or prev is None else 'صعودی' if v>prev else 'نزولی' if v<prev else 'فلت')
   ws.append(list(row)+values+trends)
  info=wb.create_sheet('خلاصه')
  info.append(['نماد','تایم‌فریم','منبع','آخرین کندل','اصلی ۱','فرعی ۱','اصلی ۲','فرعی ۲'])
  info.append([symbol,'روزانه' if tf==1440 else f'{tf} دقیقه',source,summary['last'],*summary['signals']])
  for sheet in wb:
   sheet.sheet_view.rightToLeft=True;sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
   for cells in sheet.iter_rows():
    for cell in cells:
     text=str(cell.value or '');color=colors.get(text,'000000')
     if sheet==info and cell.row>1:
      color=next((v for k,v in colors.items() if k in text.split('\n')[0]),color)
     cell.font=Font(name='B Zar',size=14,color=color)
     cell.alignment=Alignment(horizontal='right',vertical='center',wrap_text=True,readingOrder=2)
     if cell.row==1:
      cell.fill=PatternFill('solid',fgColor='17365D');cell.font=Font(name='B Zar',size=14,bold=True,color='FFFFFF')
     elif isinstance(cell.value,(int,float)):cell.number_format='#,##0.##'
   sheet.row_dimensions[1].height=30
   for col in range(1,sheet.max_column+1):sheet.column_dimensions[get_column_letter(col)].width=32 if sheet==info else 19
  info.row_dimensions[2].height=85
  tmp=path.with_suffix('.tmp.xlsx')
  try:
   wb.save(tmp);os.replace(tmp,path)
  except PermissionError as exc:
   raise PermissionError(f'داده در بانک محفوظ است؛ فایل اکسل را ببندید و دوباره اجرا کنید: {path.name}') from exc
  finally:
   wb.close()
   if tmp.exists():tmp.unlink()
 def list_series(self):
  return [dict(id=r[0],symbol=r[1],tf=r[2],source=r[3],summary=json.loads(r[4])) for r in self.db.execute('SELECT s.id,s.symbol,s.tf,s.source,s.summary FROM series s JOIN symbols t ON s.symbol=t.name WHERE s.visible=1 AND s.summary IS NOT NULL ORDER BY t.position,s.tf,s.source')]
 def hide(self,sid):
  with self.db:self.db.execute('UPDATE series SET visible=0 WHERE id=?',(sid,))
  self.sync_exports()
 def move(self,symbol,delta):
  names=[r[0] for r in self.db.execute('SELECT name FROM symbols ORDER BY position,name')]
  if symbol not in names:return
  i=names.index(symbol);j=i+delta
  if not 0<=j<len(names):return
  names[i],names[j]=names[j],names[i]
  with self.db:
   for i,name in enumerate(names):self.db.execute('UPDATE symbols SET position=? WHERE name=?',(i,name))
  self.sync_exports()

import unittest,tempfile,json,csv
from pathlib import Path
from core import Store,analyze,parse_text,inspect_file

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Store(self.tmp.name)
  self.rows=[[f'2026-01-{i//24+1:02}',f'{i%24:02}:00',100.+i,103.+i,99.+i,102.+i,500.] for i in range(90)]
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def batch(self,source='file',tf=60):return dict(symbol='اهرم',tf=tf,source=source,rows=self.rows)
 def test_idempotent_and_append(self):
  self.assertEqual(self.s.import_batches([self.batch()]),(90,0))
  path=next((Path(self.tmp.name)/'outputs').rglob('*.csv'));before=path.read_bytes()
  self.assertEqual(self.s.import_batches([self.batch()]),(0,0));self.assertEqual(before,path.read_bytes())
  self.rows.append(['2026-01-04','18:00',190.,193.,189.,192.,500.]);self.assertEqual(self.s.import_batches([self.batch()]),(1,0));self.assertTrue(path.read_bytes().startswith(before))
  self.rows[20][3]+=1;self.assertEqual(self.s.import_batches([self.batch()]),(0,1))
 def test_sources_hide_restore_order(self):
  self.s.import_batches([self.batch('file',1440),self.batch('finpy',1440)])
  self.assertEqual(len(self.s.list_series()),2)
  sid=self.s.list_series()[0]['id'];self.s.hide(sid);self.assertEqual(len(self.s.list_series()),1);self.assertEqual(len(self.s.rows(sid)),90)
  self.s.import_batches([self.batch('file',1440)]);self.assertEqual(len(self.s.list_series()),2)
  b=self.batch();b['symbol']='خودرو';self.s.import_batches([b]);self.s.move('خودرو',-1);self.assertEqual(self.s.list_series()[0]['symbol'],'خودرو')
 def test_parser(self):
  r=parse_text('<Ticker>,<Per>,<DTYYYYMMDD>,<TIME>,<Open>,<High>,<Low>,<Close>,<Vol>\nاهرم,5,20260101,090000,100,110,90,105,3')
  self.assertEqual(r[0]['row'][:2],['2026-01-01','09:00']);self.assertEqual(r[0]['symbol'],'اهرم')
  with self.assertRaises(ValueError):parse_text('bad,data')
 def test_short(self):
  s,_=analyze(self.rows[:4]);self.assertEqual(s['signals'],['داده کافی نیست']*4)
 def test_atomic(self):
  with self.assertRaises(ValueError):self.s.import_batches([self.batch(),dict(symbol='',tf=0,source='file',rows=self.rows)])
  self.assertEqual(self.s.list_series(),[])
if __name__=='__main__':unittest.main()

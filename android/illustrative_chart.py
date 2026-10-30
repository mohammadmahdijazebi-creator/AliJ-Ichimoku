"""Illustrative geometric wave sketch, NOT a validated NEoWave count."""
from pathlib import Path
import json, shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from wave_review import swings, paint_persian, font


def build(d, symbol, source, out):
    from two_session_basis import aggregate
    from daily_reference_basis import cash_points, references
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    b=aggregate(d)
    b.to_csv(out/'two_session_OHLC.csv',index=False,encoding='utf-8-sig')
    points=[]
    for r in b.itertuples():
        for kind in ('L','H'):
            points.append(dict(index=len(points),block=r.block,start_date=r.start_date,end_date=r.end_date,kind=kind,price=r.low if kind=='L' else r.high,incomplete=r.incomplete,order='conventional_LH_not_observed'))
    p=pd.DataFrame(points)
    p.to_csv(out/'two_session_conventional_path.csv',index=False,encoding='utf-8-sig')
    y=p.price.to_numpy(); x=np.arange(len(y)); piv=np.array(swings(y,.08),dtype=int)
    rows=[]
    for k,(a,b) in enumerate(zip(piv[:-1],piv[1:]),1):
        rows.append(dict(label=f'W{k}',start=int(a),end=int(b),start_price=y[a],end_price=y[b],change_pct=100*(y[b]/y[a]-1),provisional=k==len(piv)-1,type='geometric_8pct_not_NeoWave'))
    pd.DataFrame(rows).to_csv(out/'illustrative_labels.csv',index=False,encoding='utf-8-sig')
    refs=pd.DataFrame(references(cash_points(d)))
    refs.to_csv(out/'three_reference_pivots.csv',index=False,encoding='utf-8-sig')
    valid=len(refs)==3
    p1,p2,p3=refs.price.tolist() if valid else (0,0,0)
    pd.DataFrame([dict(ratio=r,price=p3+r*(p2-p1),conditional=True) for r in (.618,1,1.272,1.618)] if valid else [],columns=['ratio','price','conditional']).to_csv(out/'conditional_fibonacci.csv',index=False,encoding='utf-8-sig')
    # Place preserved references in their containing two-session block, without claiming chronology.
    refx=[]
    for r in refs.itertuples():
        q=p[(p.start_date<=r.date)&(p.end_date>=r.date)]
        refx.append(float(q['index'].mean()))

    def draw(a,b,name,targets=False):
        fig,ax=plt.subplots(figsize=(18,11),facecolor='#f7f9ff')
        fig.subplots_adjust(top=.87,bottom=.30,left=.07,right=.96)
        ax.set_facecolor('#f3f6fc')
        ax.plot(x[a:b+1],y[a:b+1],color='#8d9ab1',lw=.65,alpha=.6,label='Two-session conventional L-H path')
        visible=[r for r in rows if r['end']>=a and r['start']<=b]
        for r in visible:
            u,v=r['start'],r['end'];col='#00876c' if y[v]>y[u] else '#da3755' if y[v]<y[u] else '#de8c18'
            ax.plot([u,v],[y[u],y[v]],color=col,lw=2)
            if a<=v<=b:
                ax.annotate(r['label']+('*' if r['provisional'] else ''),(v,y[v]),xytext=(0,12 if y[v]>=y[u] else -19),textcoords='offset points',ha='center',fontsize=8,color=col,fontweight='bold',bbox=dict(fc='white',ec='none',alpha=.8,pad=1))
        # Descriptive parallel envelope fitted in log-price space, not Neely channel rules.
        xx=x[a:b+1]; yy=np.log(y[a:b+1]); fit=np.polyfit(xx,yy,1) if len(xx)>1 else [0,yy[0]];mid=np.polyval(fit,xx);res=yy-mid
        lo=np.exp(mid+res.min());hi=np.exp(mid+res.max())
        ax.fill_between(xx,lo,hi,color='#6375dd',alpha=.09)
        ax.plot(xx,lo,color='#6246c6',lw=1.6,label='Geometric log-regression envelope (NOT Neely)')
        ax.plot(xx,hi,color='#6246c6',lw=1.6);ax.plot(xx,np.exp(mid),'--',color='#6246c6',lw=1)
        for k,(r,rx) in enumerate(zip(refs.itertuples(),refx)):
            if a<=rx<=b:
                ax.scatter(rx,r.price,s=65,color='#f0a400',edgecolors='#593f00',zorder=7)
                ax.annotate(f'{r.id}{"*" if r.provisional else ""}: {r.price:,.0f}\n{r.change_pct if r.change_pct is not None else float("nan"):+.2f}%',(rx,r.price),xytext=(.74,[.16,.85,.48][k]),textcoords='axes fraction',fontsize=10,fontweight='bold',bbox=dict(fc='#fff2b3',ec='#c18a00',boxstyle='round,pad=.4'),arrowprops=dict(arrowstyle='-',color='#987000'))
        end=b+max(10,(b-a)*(.45 if targets else .03))
        if targets and valid:
            span=p2-p1
            for fi,(ratio,col) in enumerate([(.618,'#007d78'),(1,'#164dbe'),(1.272,'#853cb0'),(1.618,'#b33b61')]):
                target=p3+ratio*span
                ax.hlines(target,b+5,end-2,color=col,lw=2)
                ax.annotate(f'FIB {ratio:g} | {target:,.0f}',(b+(end-b)*.53,target),xytext=(.88,.66+.085*fi),textcoords='axes fraction',ha='center',color='white',fontsize=11,fontweight='bold',bbox=dict(fc=col,ec=col,boxstyle='round,pad=.4'),arrowprops=dict(arrowstyle='-',color=col,lw=1))
            ax.plot([refx[-1],b+(end-b)*.8],[p3,p3+span],'--',color='#007d78',lw=1.5,label='Conditional illustration, NOT a forecast')
            ax.axhline(p3,color='#d24646',ls=':',alpha=.5)
        ax.set_xlim(a-3,end);ax.set_yscale('log');ax.grid(alpha=.16)
        ticks=np.linspace(a,b,7,dtype=int);ax.set_xticks(ticks);ax.set_xticklabels(p.end_date.iloc[ticks],fontsize=9)
        ax.set_ylabel('Price (source units), log');ax.legend(loc='upper left',fontsize=8)
        path=out/name;fig.savefig(path,dpi=160);plt.close(fig)
        paint_persian(path,symbol+' | طرح تقریبی موجی و کانال هندسی | شمارش تأییدشدهٔ نئوویو نیست',[
            'مبنای داده دو جلسهٔ معاملاتی است؛ ترتیب کف سپس سقف قراردادی است و زمان واقعی وقوع نقاط استفاده نشده است.',
            'لیبل‌های W شمارهٔ حرکت‌های هندسی با برگشت ۸ درصد هستند؛ لیبل ساختاری یا درجه‌بندی امواج گلن نیلی نیستند.',
            'کانال بنفش پوش موازی رگرسیون لگاریتمی همین بخش تصویر است؛ کانال نیلی یا سیگنال حمایت و مقاومت نیست.',
            'سه پیوت زرد از مسیر روزانه با آستانهٔ برگشت ۸ درصد استخراج شده‌اند؛ درصدها نسبت به پیوت قبلی است. ستاره یعنی نقطه یا حرکت موقت.',
            'کادرها سطوح فیبوناچی مشروط هستند: قیمت پیوت سوم به‌علاوهٔ نسبت ضرب‌در اختلاف پیوت دوم و اول.',
            'فرض سناریو پایان حرکت برگشتی در پیوت سوم است؛ عبور از آن خلاف جهت سناریو، مبنا را نیازمند بازبینی می‌کند.',
            'ضخامت کادرها بیانگر محدودهٔ احتمالی قیمت نیست؛ احتمال موفقیت، هدف زمانی و تأیید نیلی محاسبه نشده است.',
            'خط‌چین آینده صرفاً تصویرسازی سناریو است، نه پیش‌بینی. این تصویر توصیهٔ معامله نیست.'
        ],font())

    draw(0,len(y)-1,'overview.png')
    start=int(piv[max(0,len(piv)-15)]) if len(piv) else 0
    draw(start,len(y)-1,'latest_targets.png',True)
    for page,idx in enumerate(range(0,len(piv)-1,22),1):
        draw(int(piv[idx]),int(piv[min(idx+22,len(piv)-1)]),f'History_{page:02d}.png')

    (out/'status.json').write_text(json.dumps(dict(symbol=symbol,source=source,complete_neely_count=False,labels='geometric 8 percent',channel='log regression envelope',waves=len(rows),targets_available=valid,fib_formula='P3 + ratio*(P2-P1)'),ensure_ascii=False,indent=2),encoding='utf-8')

"""Display-only rules agreed with the user; no trading orders or forecasts."""
import re
STATES=('همگرایی صعودی','واگرایی صعودی','همگرایی نزولی','واگرایی نزولی')
MATRIX=(
 ('خرید قوی',None,None,'فروش با احتیاط'),
 ('خرید قوی',None,None,'فروش'),
 (None,'خرید با احتیاط','فروش قوی',None),
 (None,'خرید','فروش قوی',None),
)
DISPLAY_ORDER=(0,2,1,3)

def state(text):
    first=text.split('\n')[0]
    return next((s for s in STATES if first.startswith(s)),None)

def timeframe(tf):
    return 'روزانه' if tf==1440 else f'{tf} دقیقه'

def duration(minutes):
    days,rem=divmod(minutes,1440);hours,mins=divmod(rem,60)
    return ' و '.join(f'{n} {unit}' for n,unit in ((days,'روز'),(hours,'ساعت'),(mins,'دقیقه')) if n) or '۰ دقیقه'

def assess(summary,tf):
    signals=summary.get('signals',[])
    if len(signals)<2:return 'داده کافی نیست',None,0
    main,sub=map(state,signals[:2])
    if main is None or sub is None:return 'داده کافی نیست',None,0
    action=MATRIX[STATES.index(main)][STATES.index(sub)]
    if action is None:return 'ترکیب ناممکن؛ نیازمند بررسی',None,0
    # Only the detail of main 1, never its headline count or main 2.
    detail=signals[0].partition('\n')[2]
    count=sum(int(n) for n in re.findall(r'(\d+)\s+تا\s+فلت',detail))
    return action,count*tf,count

def selected_rows(rows):
    top=sorted({r['tf'] for r in rows},reverse=True)[:3]
    return sorted((r for r in rows if r['tf'] in top),key=lambda r:(-r['tf'],r['source']))

def badge_parts(row):
    action,minutes,count=assess(row['summary'],row['tf'])
    timing=('زمان: '+duration(minutes)) if minutes else ('فلت ندارد؛ زمان تعیین نشده' if minutes==0 else 'زمان نامشخص')
    color='#00cc44' if action.startswith('خرید') else '#ff3333' if action.startswith('فروش') else '#ff9900'
    return timeframe(row['tf']),action,timing,color

def badge(row):
    tf,action,timing,color=badge_parts(row)
    return f'{tf} | {action} | {timing}',color

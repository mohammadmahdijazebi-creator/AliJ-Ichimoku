"""
کش دیتا + دو سبک نمودار، با پیدا کردن خودکار فایل‌ها.

اجرا:
  python3 cashdata.py                 -> همه‌ی فایل‌های txt/csv کنار برنامه و پوشه‌ی فعلی را خودش پیدا و پردازش می‌کند
  python3 cashdata.py a.txt b.csv     -> فقط همین فایل‌ها (کشیدن و رها کردن فایل روی برنامه هم کار می‌کند)
گزینه‌ها: --pivots 25 (حساسیت سبک اول)  --zoom 700  --waves i,j,k,l  --major 40  --minor 8

خروجی کنار هر فایل ورودی:
  <name>_cashdata.csv / .txt   کش دیتای روزانه (idx,date,price,type)
  <name>_pivots.csv            نقاط عطف سبک اول
  <name>_cashdata_wave.png     سبک ۱: کش دیتای H/L، کانال 0-2، ناحیه موج ۴ و هدف موج ۵
  <name>_neowave.png           سبک ۲: کش دیتای سه‌ماهه (شمسی)، مونوویوهای بزرگ با سال شمسی،
                               ضریب رشد، الگوی مثلثی/اصلاحی A,B,C,... و اهداف فیبوناچی
  <name>_neowave.csv           پیوت‌های سبک ۲
"""
import sys, os, glob, argparse, warnings
warnings.filterwarnings('ignore')
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt


# ---------------- ورودی ----------------
def load(path):
    d = pd.read_csv(path, sep=None, engine='python', index_col=False)
    d.columns = [str(c).strip().strip('<>').lower() for c in d.columns]
    ren = {}
    for c in d.columns:
        if c in ('dtyyyymmdd', 'date', 'datetime'): ren[c] = 'date'
        elif c.startswith('open') and 'int' not in c: ren[c] = 'open'
        elif c.startswith('high'): ren[c] = 'high'
        elif c.startswith('low'): ren[c] = 'low'
        elif c.startswith('close') or c == 'last': ren[c] = 'close'
    d = d.rename(columns=ren).loc[:, lambda x: ~x.columns.duplicated()]
    need = {'date', 'open', 'high', 'low', 'close'}
    if not need <= set(d.columns):
        raise ValueError(f'ستون لازم پیدا نشد: {need - set(d.columns)}')
    s = d['date'].astype(str).str.replace(r'\D', '', regex=True).str[:8]
    d['date'] = pd.to_datetime(s, format='%Y%m%d', errors='coerce')
    for c in ('open', 'high', 'low', 'close'):
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d.dropna(subset=['date', 'open', 'high', 'low', 'close']).sort_values('date').reset_index(drop=True)
    if len(d) < 50: raise ValueError('داده کافی نیست')
    return d


def discover():
    here = [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]
    seen, out = set(), []
    for h in here:
        for ext in ('*.txt', '*.csv', '*.TXT', '*.CSV'):
            for f in glob.glob(os.path.join(h, ext)):
                f = os.path.abspath(f); b = os.path.basename(f).lower()
                if f in seen or any(k in b for k in ('_cashdata', '_pivots', '_neowave', 'readme')): continue
                seen.add(f); out.append(f)
    return sorted(out)


# ---------------- تاریخ شمسی ----------------
def g2j(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    jy = -1595 + 33 * (days // 12053); days %= 12053
    jy += 4 * (days // 1461); days %= 1461
    if days > 365: jy += (days - 1) // 365; days = (days - 1) % 365
    if days < 186: jm = 1 + days // 31; jd = 1 + days % 31
    else: jm = 7 + (days - 186) // 30; jd = 1 + (days - 186) % 30
    return jy, jm, jd


# ---------------- کش دیتا ----------------
def to_cash(d):
    """ترتیب درون‌روزی نامعلوم: کلوز>=اوپن => Low سپس High، وگرنه High سپس Low (تقریبی)."""
    rows = []
    for r in d.itertuples():
        if r.high == r.low: pair = [('H', r.high)]
        elif r.close >= r.open: pair = [('L', r.low), ('H', r.high)]
        else: pair = [('H', r.high), ('L', r.low)]
        rows += [(r.date, p, t) for t, p in pair]
    c = pd.DataFrame(rows, columns=['date', 'price', 'type'])
    c = c[c.price.diff().fillna(1) != 0].reset_index(drop=True)
    p = c.price.values
    keep = sorted(set([0] + [i for i in range(1, len(c) - 1) if (p[i]-p[i-1]) * (p[i+1]-p[i]) < 0] + [len(c) - 1]))
    c = c.loc[keep].reset_index(drop=True)
    c.insert(0, 'idx', range(len(c)))
    return c


def zigzag(p, pct):
    piv = [0]; direction = 0; ext = 0
    for i in range(1, len(p)):
        if direction == 0:
            if abs(p[i] / p[0] - 1) * 100 >= pct:
                direction = 1 if p[i] > p[0] else -1; ext = i
        elif direction == 1:
            if p[i] > p[ext]: ext = i
            elif (p[ext] - p[i]) / p[ext] * 100 >= pct: piv.append(ext); direction = -1; ext = i
        else:
            if p[i] < p[ext]: ext = i
            elif (p[i] - p[ext]) / p[ext] * 100 >= pct: piv.append(ext); direction = 1; ext = i
    piv.append(ext)
    return sorted(set(piv))


def find_waves(p, piv):
    v = [p[i] for i in piv]
    for k in range(len(piv) - 4, -1, -1):
        a, b, c_, d_ = v[k:k+4]
        if a < b and a < c_ < b and d_ > b and a < min(v[k+1:]):
            return [piv[k], piv[k+1], piv[k+2], piv[k+3]]
    return None


# ---------------- سبک ۱ ----------------
def wave_chart(c, p, piv, name, base, zoom, waves):
    w = [piv[int(x)] for x in waves.split(',')] if waves else find_waves(p, piv)
    n = len(p)
    fig, ax = plt.subplots(figsize=(14, 7))
    lo = max(0, (w[0] if w else n - 600) - zoom)
    ax.plot(range(lo, n), p[lo:], color='navy', lw=.7); ax.set_yscale('log')
    xr = n + 400
    labels = []
    if w:
        for k, i in enumerate(w):
            ax.annotate(str(k), (i, p[i]), fontsize=14, color='red', ha='center', va='bottom' if k % 2 else 'top')
        i0, i1, i2, i3 = w
        sl = (np.log(p[i2]) - np.log(p[i0])) / (i2 - i0)
        x = np.arange(i0, xr)
        bl = np.log(p[i0]) + sl * (x - i0)
        up = bl + (np.log(p[i1]) - (np.log(p[i0]) + sl * (i1 - i0)))
        ax.plot(x, np.exp(bl), '--', color='purple', lw=1); ax.plot(x, np.exp(up), '--', color='purple', lw=1)
        w3 = p[i3] - p[i2]
        ax.axhline(p[i1], color='r', ls=':'); labels.append(ax.text(n + 10, p[i1] * 1.01, f'invalid < {p[i1]:.4g} (W1 high)'))
        z1, z2 = p[i3] - 0.5 * w3, p[i3] - 0.236 * w3
        ax.axhspan(z1, z2, color='orange', alpha=.2); labels.append(ax.text(n + 10, (z1 * z2) ** .5, f'W4 zone {z1:.4g}-{z2:.4g}'))
        w4 = p[i3] - 0.382 * w3
        t1, t2 = w4 + 0.618 * (p[i3] - p[i0]), w4 + 1.0 * (p[i3] - p[i0])
        ax.axhspan(t1, t2, color='green', alpha=.15); labels.append(ax.text(n + 10, (t1 * t2) ** .5, f'W5 target {t1:.4g}-{t2:.4g}'))
        ax.set_ylim(min(p[lo:]) * .9, max(t2, max(p[lo:])) * 1.15)
    else:
        print('  سبک ۱: الگوی 0-1-2-3 پیدا نشد؛ فقط کش دیتا رسم شد.')
    ax.set_xlim(lo, xr)
    ax.set_title(f'{name} cash-data (1 H/L = 1 time unit), log, channel 0-2 + parallel via 1')
    ax.set_xlabel('H/L units'); ax.grid(alpha=.2)
    # Separate labels in display coordinates: a price offset is unreliable
    # on a logarithmic axis. Keep a small physical gap between text boxes.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    previous_top = None
    for label in sorted(labels, key=lambda t:t.get_window_extent(renderer).y0):
        box = label.get_window_extent(renderer)
        shift = max(0, previous_top + 7 - box.y0) if previous_top is not None else 0
        if shift:
            x, y = ax.transData.transform(label.get_position())
            label.set_position(ax.transData.inverted().transform((x, y + shift)))
        previous_top = box.y1 + shift
        label.set_bbox(dict(facecolor='white', alpha=.65, edgecolor='none', pad=1.5))
    fig.savefig(base + '_cashdata_wave.png', dpi=110, bbox_inches='tight'); plt.close(fig)
    return w


# ---------------- سبک ۲: نیوویو (سه‌ماهه شمسی) ----------------
def quarterly(d):
    jj = [g2j(t.year, t.month, t.day) for t in d.date]
    d = d.assign(jy=[j[0] for j in jj], q=[(j[1] - 1) // 3 for j in jj])
    g = d.groupby(['jy', 'q'], sort=True)
    return pd.DataFrame({'date': g.date.last(), 'open': g.open.first(), 'high': g.high.max(),
                         'low': g.low.min(), 'close': g.close.last(), 'jy': g.jy.first().values}).reset_index(drop=True)


def neowave_chart(d, name, base, major=40, minor=8):
    qd = quarterly(d); c = to_cash(qd); p = c.price.values; n = len(p)
    piv = zigzag(p, major)
    jy = lambda i: g2j(c.date[i].year, c.date[i].month, c.date[i].day)[0]
    fig, ax = plt.subplots(figsize=(15, 7))
    ax.plot(range(n), p, color='navy', lw=1.8); ax.set_yscale('log')
    rows = []
    for k, i in enumerate(piv):
        up = (k + 1 < len(piv) and p[piv[k + 1]] > p[i]) if k + 1 < len(piv) else (p[i] < p[piv[k - 1]] if k else False)
        ax.annotate(str(jy(i)), (i, p[i]), color='red', fontsize=12, fontweight='bold', ha='center',
                    va='top' if up else 'bottom', xytext=(0, -8 if up else 8), textcoords='offset points')
        rows.append((i, str(c.date[i].date()), jy(i), p[i]))
        if k > 0:
            j = piv[k - 1]
            if p[i] / p[j] >= 3:
                ax.add_patch(plt.Rectangle((j, p[j]), i - j, p[i] - p[j], color='peachpuff', alpha=.5, lw=0))
                ax.text((i + j) / 2, p[j] * 1.1, f'x{p[i]/p[j]:.0f}', color='green', fontsize=12, fontweight='bold', ha='center')
    pd.DataFrame(rows, columns=['idx', 'date', 'jalali_year', 'price']).to_csv(base + '_neowave.csv', index=False)

    # الگوی اصلاحی اخیر: از آخرین سقف ماژور به بعد، با زیگزاگ ریزتر
    hi = [i for i in piv if i < n - 1 and (i == max(piv, key=lambda k: p[k]) or p[i] > p[min(piv[-1], n - 1)])]
    start = max([i for i in piv if p[i] >= p[piv[-1]] * 0 and i < piv[-1]] or [piv[-1]])
    # آخرین قله‌ی ماژور (پیوت بالا)
    tops = [i for k, i in enumerate(piv) if (k + 1 < len(piv) and p[piv[k + 1]] < p[i]) or (k == len(piv) - 1 and p[i] > p[piv[k - 1]])]
    msg = ''
    if tops:
        t = tops[-1]
        sub = zigzag(p[t:], minor); sub = [t + s for s in sub]
        if len(sub) >= 5:
            letters = 'ABCDEFGHIJKLMNOP'
            pts = sub[1:1 + len(letters)]
            for L, i in zip(letters, pts):
                ax.annotate(L, (i, p[i]), color='olive', fontsize=11, ha='center',
                            va='bottom' if p[i] >= p[min(n - 1, i + 1)] and p[i] > np.median(p[t:]) else 'top')
            highs = [i for i in sub if p[i] >= np.median(p[sub])]; lows = [i for i in sub if p[i] < np.median(p[sub])]
            x = np.arange(t, n + 40)
            for grp in (highs, lows):
                if len(grp) >= 2:
                    a, b = np.polyfit(grp, np.log(p[grp]), 1)
                    ax.plot(x, np.exp(a * x + b), color='green', lw=.8)
            # هدف: فیبوناچی روی آخرین پای بزرگ صعودی قبل از قله
            k = piv.index(t); base_i = piv[k - 1] if k > 0 else 0
            leg = p[t] - p[base_i]; low = min(p[t:])
            for f, ls in ((1.0, ':'), (1.618, ':')):
                tg = low + f * leg
                ax.axhline(tg, color='olive', ls=ls, lw=.8); ax.text(n + 42, tg, f'FE {f*100:.0f}  {tg:.4g}', color='olive', va='bottom')
            msg = f'  سبک ۲: قله‌ی ماژور {jy(t)}، {len(sub)-1} پیوت اصلاحی (A..)، پای مبنا {p[base_i]:.4g}->{p[t]:.4g}'
        else:
            msg = '  سبک ۲: بعد از آخرین قله ماژور پیوت اصلاحی کافی (minor کمتر کن) پیدا نشد'
    # برچسب محور زمان به سال شمسی
    ticks = [i for i in range(1, n) if jy(i) != jy(i - 1)][::2]
    ax.set_xticks(ticks); ax.set_xticklabels([str(jy(i)) for i in ticks], rotation=0)
    ax.set_xlim(-2, n + 120); ax.grid(alpha=.2)
    ax.set_title(f'{name} NeoWave style - 3-month cash data (Jalali quarters), log scale')
    fig.savefig(base + '_neowave.png', dpi=110, bbox_inches='tight'); plt.close(fig)
    print(msg)


# ---------------- اجرا ----------------
def process(path, a):
    base = os.path.splitext(path)[0]; name = os.path.basename(base)
    d = load(path); c = to_cash(d)
    c.to_csv(base + '_cashdata.csv', index=False); c.to_csv(base + '_cashdata.txt', index=False, sep='\t')
    p = c.price.values; piv = zigzag(p, a.pivots)
    pd.DataFrame({'pivot_no': range(len(piv)), 'idx': piv, 'date': c.date[piv].values, 'price': p[piv]}).to_csv(base + '_pivots.csv', index=False)
    w = wave_chart(c, p, piv, name, base, a.zoom, a.waves)
    print(f'  روزانه={len(d)} کش‌دیتا={len(p)} پیوت={len(piv)} امواج={[(i, round(p[i], 2), str(c.date[i].date())) for i in w] if w else None}')
    if a.neowave:
        neowave_chart(d, name, base, a.major, a.minor)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='*')
    ap.add_argument('--pivots', type=float, default=25); ap.add_argument('--zoom', type=int, default=700)
    ap.add_argument('--waves', default=''); ap.add_argument('--major', type=float, default=40)
    ap.add_argument('--minor', type=float, default=8)
    ap.add_argument('--neowave', action='store_true', help='سبک ۲ (آزمایشی، پیش‌فرض خاموش)')
    a = ap.parse_args()
    files = a.files or discover()
    if not files: sys.exit('هیچ فایل txt/csv پیدا نشد؛ فایل‌ها را کنار برنامه بگذار.')
    for f in files:
        print('>>', os.path.basename(f))
        try: process(f, a)
        except Exception as e: print('  رد شد:', e)

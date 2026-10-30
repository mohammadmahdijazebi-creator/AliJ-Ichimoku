"""Daily review layout; heuristic swings, never a verified NeoWave count."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager
import arabic_reshaper
from bidi.algorithm import get_display


def rtl(text):
    return get_display(arabic_reshaper.reshape(str(text)), base_dir='R')


def font():
    import os
    bundled = Path(__file__).resolve().parent / 'fonts'
    windows = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    local = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Microsoft/Windows/Fonts'
    # Explicit paths also work when matplotlib's installed-font cache is stale.
    for folder in (bundled, windows, local):
        if folder.is_dir():
            for candidate in sorted(folder.iterdir()):
                if candidate.suffix.lower() in ('.ttf', '.otf') and candidate.stem.lower().replace(' ', '').replace('-', '') in ('bzar', 'zar'):
                    return FontProperties(fname=str(candidate), size=15)
    for entry in fontManager.ttflist:
        if entry.name.lower().replace(' ', '') in ('bzar', 'zar'):
            return FontProperties(fname=entry.fname, size=15)
    fallback = bundled / 'Vazir.ttf'
    if fallback.exists():
        return FontProperties(fname=str(fallback), size=15)
    return FontProperties(family='DejaVu Sans', size=15)


def paint_persian(output, title, lines, properties):
    """Shape once, with per-glyph font fallback and a shared baseline."""
    from PIL import Image, ImageDraw, ImageFont
    from matplotlib.font_manager import findfont
    from matplotlib.ft2font import FT2Font
    import unicodedata
    path = properties.get_file() or findfont(properties)
    fallback = Path(__file__).resolve().parent / 'fonts' / 'Vazir.ttf'
    paths = [path, str(fallback) if fallback.exists() else findfont('DejaVu Sans')]
    faces = [ImageFont.truetype(p, round(17*160/72), layout_engine=ImageFont.Layout.BASIC) for p in paths]
    maps = [FT2Font(p).get_charmap() for p in paths]

    def runs(text):
        result = []
        for char in rtl(text):
            if unicodedata.category(char) == 'Cf':
                continue  # invisible bidi/joining controls must not become boxes
            index = next((i for i, cmap in enumerate(maps) if ord(char) in cmap), 1)
            if result and result[-1][0] == index:
                result[-1] = (index, result[-1][1]+char)
            else:
                result.append((index, char))
        return result

    def width(text):
        return sum(draw.textlength(part, font=faces[i]) for i,part in runs(text))

    def put(right, top, text):
        x = right-width(text)
        baseline = top+max(face.getmetrics()[0] for face in faces)
        for i, part in runs(text):
            draw.text((x, baseline), part, font=faces[i], fill='black', anchor='ls')
            x += draw.textlength(part, font=faces[i])
    with Image.open(output) as original:
        image = original.convert('RGB')
    draw = ImageDraw.Draw(image)
    w, h = image.size
    put(int(.84*w), int(.055*h), title)
    y = int(.82*h)
    spacing = round(27*160/72)
    for line in lines:
        # Wrap logical text before shaping; keep 17 pt rather than shrinking.
        wrapped, current = [], ''
        for word in line.split():
            trial = (current+' '+word).strip()
            if current and width(trial) > .88*w:
                wrapped.append(current)
                current = word
            else:
                current = trial
        wrapped.append(current)
        for text in wrapped:
            if y+spacing > image.height:
                expanded = Image.new('RGB', (w, y+spacing+24), 'white')
                expanded.paste(image, (0,0))
                image = expanded
                draw = ImageDraw.Draw(image)
            put(int(.94*w), y, text)
            y += spacing
    image.save(output, dpi=(160,160))


def swings(values, threshold):
    """Close-based reversal swings; last extreme remains provisional."""
    if not len(values):
        return []
    result = [0]
    extreme = 0
    direction = 0
    for i in range(1, len(values)):
        change = values[i] / values[extreme] - 1
        if direction == 0:
            if abs(change) >= threshold:
                direction = 1 if change > 0 else -1
                extreme = i
        elif direction > 0:
            if values[i] >= values[extreme]:
                extreme = i
            elif change <= -threshold:
                result.append(extreme)
                direction, extreme = -1, i
        else:
            if values[i] <= values[extreme]:
                extreme = i
            elif change >= threshold:
                result.append(extreme)
                direction, extreme = 1, i
    if extreme != result[-1]:
        result.append(extreme)
    return result


def review_chart(d, symbol, source, output):
    d = d.sort_values('date').reset_index(drop=True)
    f = font()
    fig, ax = plt.subplots(figsize=(15, 9))
    fig.subplots_adjust(bottom=.29, right=.84)
    try:
        valid = len(d) >= 3 and np.isfinite(d[['low','high','close']].to_numpy(dtype=float)).all() and (d[['low','high','close']] > 0).all().all()
        if not valid:
            lines = ['نمودار سناریویی تولید نشد؛ داده‌ها نیاز به بررسی دارند.']
        else:
            values = d.close.to_numpy(dtype=float)
            major = swings(values, .08)[-7:]
            minor = swings(values, .03)
            n = len(d)
            start = max(0, major[0]-12) if len(major)>2 else max(0,n-200)
            s = d.iloc[start:]
            x = np.repeat(s.index.to_numpy()*2, 2)+np.tile([0,1],len(s))
            ax.plot(x,s[['low','high']].to_numpy().ravel(),color='#337ab0',lw=.7)
            ax.plot(x,s[['high','low']].to_numpy().ravel(),color='#69a5bf',lw=.45,alpha=.4)
            visible = [i for i in minor if i>=start]
            ax.plot(np.array(visible)*2,values[visible],color='#999999',lw=.7,alpha=.6)
            ax.plot(np.array(major)*2,values[major],color='#243f70',lw=1.4)
            for k,i in enumerate(major):
                ax.annotate(f'P{k}?\n{values[i]:,.0f}',(2*i,values[i]),xytext=(0,15 if k%2 else -28),textcoords='offset points',ha='center',fontsize=10)
            # Regression envelope is a guide, not an Elliott channel rule.
            xx = np.arange(start,n)
            slope, intercept = np.polyfit(xx,np.log(values[start:]),1)
            residual = np.log(values[start:])-(slope*xx+intercept)
            guide = np.array([start,n+20])
            for shift in (residual.min(),residual.max()):
                ax.plot(guide*2,np.exp(slope*guide+intercept+shift),color='#bd9156',ls='-.',lw=1)
            lo,hi=float(s.low.min()),float(s.high.max())
            if len(major)>=2:
                a,b=values[major[-2]],values[major[-1]]
                targets=[b-(b-a)*r for r in (.382,.5,.618)]
                for j,t in enumerate(targets):
                    ax.hlines(t,2*(n-1),2*(n+22),color='#bc4d56',ls=':',lw=1)
                    ax.text(2*(n+23),t,f'R{j+1}: {t:,.0f}',fontsize=9,color='#a33746')
                ax.plot([2*(n-1),2*(n+18)],[values[-1],targets[1]],color='#bc4d56',ls='--')
                lo,hi=min(lo,*targets),max(hi,*targets)
            ax.set_yscale('log')
            ax.set_ylim(lo*.9,hi*1.15)
            ticks=np.unique(np.linspace(start,n-1,7,dtype=int))
            ax.set_xticks(ticks*2)
            ax.set_xticklabels([str(d.date.iloc[i])[:10] for i in ticks],rotation=20)
            ax.set_xlim(start*2,(n+40)*2)
            ax.grid(alpha=.17)
            lines=[
                'پیوت‌های پیشنهادی قیمت پایانی با آستانهٔ ۸ و ۳ درصد؛ آخرین پیوت ناتمام و قابل تغییر است.',
                'برچسب P شمارش موج نیست؛ زیرموج‌ها و الگوهای اختصاصی نئوویو تأیید نشده‌اند.',
                'کانال طلایی راهنمای رگرسیون لگاریتمی است؛ R بازگشت فیبوناچی آخرین حرکت، مشروط به برگشت جهت است.',
                'دو ترتیب احتمالی سقف و کف؛ شکست پیوت آخر نیازمند بازبینی است؛ خط‌چین هدف زمانی نیست.'
            ]
        last = str(d.date.iloc[-1])[:10] if len(d) else '—'
        title = f'{symbol} | سناریوی پیشنهادی روزانه | {source} | {last}'
        fig.savefig(output,dpi=160)
        paint_persian(output, title, lines, f)
    finally:
        plt.close(fig)

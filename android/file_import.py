"""Daily OHLC file import; SQLite is authoritative."""
import csv
import io
import math
import re
from datetime import datetime
from market_archive import connect


def parse_daily(text):
    sample = text.lstrip("\ufeff")
    try:
        dialect = csv.Sniffer().sniff(sample[:8192], delimiters=",;\t")
    except csv.Error:
        raise ValueError("جداکننده فایل تشخیص داده نشد.")
    reader = csv.reader(io.StringIO(sample), dialect)
    headers = next(reader, [])
    columns = {}
    for i, name in enumerate(headers):
        name = name.strip().strip("<>").lower()
        key = None
        if name in ("dtyyyymmdd", "date", "datetime"):
            key = "date"
        elif name.startswith("open") and "int" not in name:
            key = "open"
        elif name.startswith("high"):
            key = "high"
        elif name.startswith("low"):
            key = "low"
        elif name.startswith("close") or name == "last":
            key = "close"
        elif name in ("vol", "volume"):
            key = "volume"
        elif name in ("ticker", "symbol"):
            key = "symbol"
        elif name in ("per", "period", "tf"):
            key = "period"
        if key:
            columns.setdefault(key, i)
    required = {"date", "open", "high", "low", "close"}
    if not required <= columns.keys():
        raise ValueError("ستون‌های تاریخ و OHLC کامل نیستند.")

    rows, dates, symbols = [], set(), set()
    missing_volume = "volume" not in columns
    for line, cells in enumerate(reader, 2):
        if not cells or not any(c.strip() for c in cells):
            continue
        try:
            def get(key):
                return cells[columns[key]].strip()

            if "period" in columns:
                if get("period").upper() not in ("D", "D1", "DAILY", "1440"):
                    raise ValueError("فقط داده روزانه پذیرفته می‌شود")
            if "symbol" in columns:
                symbols.add(get("symbol"))
                if len(symbols) > 1:
                    raise ValueError("فایل دارای چند نماد است")

            raw = get("date")
            if re.fullmatch(r"\d{8}", raw):
                date = datetime.strptime(raw, "%Y%m%d").date()
            elif re.fullmatch(r"\d{4}[-/]\d{2}[-/]\d{2}", raw):
                date = datetime.strptime(raw.replace("/", "-"), "%Y-%m-%d").date()
            else:
                raise ValueError("قالب تاریخ روزانه نامعتبر است")
            if not 1900 <= date.year <= 2100:
                raise ValueError("تاریخ باید میلادی باشد")
            date = date.isoformat()
            if date in dates:
                raise ValueError("تاریخ تکراری؛ فایل باید روزانه باشد")

            o, h, l, c = [
                float(get(k)) for k in ("open", "high", "low", "close")
            ]
            v = 0.0 if missing_volume else float(get("volume"))
            if not all(math.isfinite(x) for x in (o, h, l, c, v)):
                raise ValueError("عدد نامعتبر")
            if min(o, h, l, c) <= 0 or v < 0:
                raise ValueError("قیمت یا حجم نامعتبر")
            if h < max(o, l, c) or l > min(o, c):
                raise ValueError("ترتیب OHLC نامعتبر")
            dates.add(date)
            rows.append([date, "00:00:00", o, h, l, c, v])
        except (ValueError, IndexError) as e:
            raise ValueError(f"خط {line}: {e}") from e
    if not rows:
        raise ValueError("فایل داده‌ای ندارد.")
    rows.sort(key=lambda r: r[0])
    return rows, missing_volume


def import_text(folder, symbol, text):
    symbol = symbol.strip().replace("ي", "ی").replace("ك", "ک")
    if not symbol or len(symbol) > 100:
        raise ValueError("نام نماد معتبر وارد کنید.")
    # Validate the entire file before opening the write transaction.
    rows, missing_volume = parse_daily(text)
    db = connect(folder)
    try:
        with db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS file_imports("
                "symbol TEXT PRIMARY KEY, imported_at TEXT, "
                "row_count INTEGER, missing_volume INTEGER)"
            )
            db.executemany(
                "INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?)",
                [(symbol, *row) for row in rows]
            )
            db.execute(
                "INSERT OR REPLACE INTO file_imports VALUES "
                "(?,datetime('now'),?,?)",
                (symbol, len(rows), int(missing_volume))
            )
        total = db.execute(
            "SELECT COUNT(*) FROM candles WHERE symbol=?", (symbol,)
        ).fetchone()[0]
        return len(rows), total, missing_volume
    finally:
        db.close()

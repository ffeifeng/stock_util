import struct

def read_day(path):
    records = []
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(32)
            if len(chunk) < 32: break
            date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
            records.append({'date': date, 'open': o/100, 'close': c/100})
    return records

def calc_ma(vals, n):
    r = [None] * len(vals)
    for i in range(n-1, len(vals)):
        r[i] = sum(vals[i-n+1:i+1]) / n
    return r

rec = read_day(r'D:\soft\new_tdx\vipdoc\sh\lday\sh603093.day')
closes = [r['close'] for r in rec]
ma30 = calc_ma(closes, 30)

print(f'{"日期":<12} {"收盘":>7} {"MA30":>7} {"阴线":>5} {"在MA30上":>8} {"离MA30%":>8}')
print('-' * 55)
for j in range(-6, 0):
    i = len(rec) + j
    r = rec[i]
    m = ma30[i]
    is_yin = r['close'] < r['open']
    above = r['close'] >= m if m else None
    pct = (r['close'] - m) / m * 100 if m else None
    pct_str = f'+{pct:.2f}%' if pct is not None else 'N/A'
    print(f'{r["date"]}   {r["close"]:>7.2f}  {m:>7.2f}  {"是" if is_yin else "否":>5}  {"是" if above else "否":>8}  {pct_str:>8}')

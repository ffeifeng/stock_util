import struct

def read_index(path):
    records = []
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(32)
            if len(chunk) < 32: break
            date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
            records.append({'date': date, 'open': o/100, 'close': c/100})
    return records

def calc_ma(values, n):
    r = [None] * len(values)
    for i in range(n-1, len(values)):
        r[i] = sum(values[i-n+1:i+1]) / n
    return r

recs   = read_index(r'D:\soft\new_tdx\vipdoc\sh\lday\sh000001.day')
closes = [r['close'] for r in recs]
ma30   = calc_ma(closes, 30)

print('  日期        收盘      MA30    离MA30    MA30斜率(5日)   阶段           当日涨跌')
print('  ' + '-'*78)

for i, r in enumerate(recs):
    if 20251220 <= r['date'] <= 20260115:
        if ma30[i] is None: continue
        vs   = (r['close'] - ma30[i]) / ma30[i] * 100
        sl   = (ma30[i] - ma30[i-5]) / ma30[i-5] * 100 if i >= 5 and ma30[i-5] else 0
        above        = r['close'] >= ma30[i]
        rising       = sl > 0.05
        falling      = sl < -0.05
        price_strong = vs > 1.0

        if above and rising and price_strong:
            phase = '★ 做波段'
        elif above and not falling:
            phase = '△ 企稳观察'
        elif abs(vs) <= 2.0 and not falling:
            phase = '△ 企稳观察'
        else:
            phase = '▼ 空仓  '

        pct = (r['close'] - recs[i-1]['close']) / recs[i-1]['close'] * 100 if i > 0 else 0
        d = str(r['date'])
        date_str = f'{d[:4]}-{d[4:6]}-{d[6:]}'
        print(f'  {date_str}  {r["close"]:>8.2f}  {ma30[i]:>8.2f}  {vs:>+6.2f}%    斜率{sl:>+6.3f}%    {phase}    {pct:>+5.2f}%')

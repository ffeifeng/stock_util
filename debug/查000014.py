import struct

def read_day_file(path):
    records = []
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32: break
                date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
                records.append({'date': date, 'open': o/100, 'high': h/100, 'low': l/100, 'close': c/100, 'vol': vol})
    except Exception as e:
        print('error:', e)
    return records

def calc_ma(values, n):
    r = [None] * len(values)
    for i in range(n-1, len(values)):
        r[i] = sum(values[i-n+1:i+1]) / n
    return r

path = r'D:\soft\new_tdx\vipdoc\sz\lday\sz000014.day'
records = read_day_file(path)
closes = [r['close'] for r in records]
ma5  = calc_ma(closes, 5)
ma10 = calc_ma(closes, 10)
ma30 = calc_ma(closes, 30)

print(f'总数据条数: {len(records)}，最新日期: {records[-1]["date"]}')
print()
print(f'  {"日期":<10} {"开":>7} {"高":>7} {"低":>7} {"收":>7}  {"MA5":>7} {"MA10":>7} {"MA30":>7}  {"涨跌%":>7}  {"量(万手)":>8}')
print('  ' + '-'*90)

last40 = records[-40:]
for i, r in enumerate(last40):
    idx = len(records) - 40 + i
    pct = (r['close'] - records[idx-1]['close']) / records[idx-1]['close'] * 100 if idx > 0 else 0
    m5  = f'{ma5[idx]:.2f}'  if ma5[idx]  else '   -'
    m10 = f'{ma10[idx]:.2f}' if ma10[idx] else '   -'
    m30 = f'{ma30[idx]:.2f}' if ma30[idx] else '   -'
    flag = ''
    if ma30[idx] and records[idx-1] and ma30[idx-1]:
        if r['close'] >= ma30[idx] and records[idx-1]['close'] < ma30[idx-1]:
            flag = ' ← 站回MA30'
        elif r['close'] < ma30[idx] and records[idx-1]['close'] >= ma30[idx-1]:
            flag = ' ← 跌破MA30'
    above = '上' if ma30[idx] and r['close'] >= ma30[idx] else '下'
    print(f'  {r["date"]}  {r["open"]:>7.2f} {r["high"]:>7.2f} {r["low"]:>7.2f} {r["close"]:>7.2f}  {m5:>7} {m10:>7} {m30:>7}  {pct:>+6.2f}%  {r["vol"]/10000:>8.1f}万  [{above}]{flag}')

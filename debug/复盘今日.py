import struct, os

def read_last(path, n=3):
    recs = []
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            total = f.tell() // 32
            start = max(0, total - n)
            f.seek(start * 32)
            while True:
                c = f.read(32)
                if len(c) < 32: break
                d, o, h, l, cl, amt, vol, _ = struct.unpack('<IIIIIfII', c)
                recs.append({'date': d, 'open': o/100, 'high': h/100,
                             'low': l/100, 'close': cl/100, 'vol': vol, 'amt': amt})
    except:
        pass
    return recs

indices = [
    ('上证指数', r'D:\soft\new_tdx\vipdoc\sh\lday\sh000001.day'),
    ('深证成指', r'D:\soft\new_tdx\vipdoc\sz\lday\sz399001.day'),
    ('创业板指', r'D:\soft\new_tdx\vipdoc\sz\lday\sz399006.day'),
    ('沪深300 ', r'D:\soft\new_tdx\vipdoc\sh\lday\sh000300.day'),
    ('科创50  ', r'D:\soft\new_tdx\vipdoc\sh\lday\sh000688.day'),
    ('北证50  ', r'D:\soft\new_tdx\vipdoc\sh\lday\sh899050.day'),
]

print('=' * 68)
print('【指数复盘】')
print(f'  {"指数":<8} {"今收":>9} {"涨跌幅":>7}  {"今开":>9} {"今高":>9} {"今低":>9}  {"日期"}')
print('  ' + '-' * 64)
for name, path in indices:
    r = read_last(path, 2)
    if len(r) < 2:
        continue
    prev, today = r[0], r[1]
    pct = (today['close'] - prev['close']) / prev['close'] * 100 if prev['close'] else 0
    d = str(today['date'])
    date_str = f'{d[:4]}-{d[4:6]}-{d[6:]}'
    print(f'  {name:<8} {today["close"]:>9.2f} {pct:>+6.2f}%  '
          f'{today["open"]:>9.2f} {today["high"]:>9.2f} {today["low"]:>9.2f}  {date_str}')

print()

# 市场宽度：涨跌家数（从扫描结果文件推断）
DATA_DIRS = {
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
}

def is_valid(code):
    c = code.lower()
    if c.startswith('bj'): return False
    num = c[2:]
    if c.startswith('sh'): return num[:3] in ['600','601','602','603','604','605','688']
    if c.startswith('sz'): return num[:3] in ['000','001','002','003','300','301']
    return False

up = down = flat = limit_up = limit_down = 0
up5 = down5 = 0

for market, d in DATA_DIRS.items():
    if not os.path.exists(d): continue
    for f in os.listdir(d):
        if not f.endswith('.day'): continue
        code = f[:-4]
        if not is_valid(code): continue
        r = read_last(os.path.join(d, f), 2)
        if len(r) < 2: continue
        prev, today = r[0], r[1]
        if prev['close'] == 0: continue
        pct = (today['close'] - prev['close']) / prev['close'] * 100
        if   pct >  9.8:  limit_up   += 1; up   += 1
        elif pct >  0.05: up          += 1
        elif pct < -9.8:  limit_down += 1; down += 1
        elif pct < -0.05: down       += 1
        else:             flat       += 1
        if pct >= 5: up5   += 1
        if pct <= -5: down5 += 1

total = up + down + flat
print('=' * 68)
print('【市场宽度】')
print(f'  上涨: {up:>4} 家   下跌: {down:>4} 家   平盘: {flat:>3} 家   共 {total} 家')
print(f'  涨停: {limit_up:>4} 家   跌停: {limit_down:>4} 家')
print(f'  涨5%+: {up5:>3} 家   跌5%+: {down5:>3} 家')
if total > 0:
    print(f'  涨跌比: {up/total*100:.1f}% / {down/total*100:.1f}%')

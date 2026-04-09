"""查看指定个股最近K线 + MA状态"""
import struct, os, sys
sys.stdout.reconfigure(encoding='utf-8')

TARGETS = [
    ('sz', '002826'),
]

DATA_DIRS = {
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
}

def read_day_file(filepath):
    records = []
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32:
                    break
                date, open_, high, low, close, amount, volume, reserved = \
                    struct.unpack('<IIIIIfII', chunk)
                records.append({
                    'date': date, 'open': open_ / 100.0, 'high': high / 100.0,
                    'low': low / 100.0, 'close': close / 100.0,
                    'volume': volume,
                })
    except Exception:
        pass
    return records

def calc_ma(values, n):
    result = []
    for i in range(len(values)):
        if i < n - 1:
            result.append(None)
        else:
            result.append(round(sum(values[i - n + 1:i + 1]) / n, 3))
    return result

def fmt(d):
    s = str(d)
    return f'{s[:4]}-{s[4:6]}-{s[6:]}'

for market, num in TARGETS:
    code = f'{market}{num}'
    path = os.path.join(DATA_DIRS[market], f'{code}.day')
    records = read_day_file(path)
    if not records:
        print(f'{code}: 文件未找到')
        continue

    closes  = [r['close'] for r in records]
    volumes = [r['volume'] for r in records]
    ma5  = calc_ma(closes, 5)
    ma10 = calc_ma(closes, 10)
    ma20 = calc_ma(closes, 20)
    ma30 = calc_ma(closes, 30)
    ma60 = calc_ma(closes, 60)

    print(f'\n{"="*65}')
    print(f'  {code}  最新 {len(records)} 根日K，最后交易日：{fmt(records[-1]["date"])}')
    print(f'{"="*65}')
    print(f'  {"日期":<12} {"开":>7} {"高":>7} {"低":>7} {"收":>7}  {"MA5":>7} {"MA20":>7} {"MA30":>7} {"MA60":>7}  {"量(万手)":>8}')
    print(f'  {"-"*90}')

    # 显示最近30根
    start = max(0, len(records) - 30)
    for i in range(start, len(records)):
        r = records[i]
        vol_w = r['volume'] / 10000
        m5  = f'{ma5[i]:>7.2f}'  if ma5[i]  else '      -'
        m20 = f'{ma20[i]:>7.2f}' if ma20[i] else '      -'
        m30 = f'{ma30[i]:>7.2f}' if ma30[i] else '      -'
        m60 = f'{ma60[i]:>7.2f}' if ma60[i] else '      -'
        close_flag = ''
        if ma30[i] and r['close'] > ma30[i] * 1.0 and (i == 0 or (ma30[i-1] and records[i-1]['close'] <= ma30[i-1])):
            close_flag = ' ★突破MA30'
        elif ma30[i] and r['close'] < ma30[i]:
            close_flag = ' ↓MA30下'
        print(f'  {fmt(r["date"]):<12} {r["open"]:>7.2f} {r["high"]:>7.2f} {r["low"]:>7.2f} {r["close"]:>7.2f}  {m5} {m20} {m30} {m60}  {vol_w:>8.1f}{close_flag}')

    # 当前状态小结
    last = records[-1]
    li = len(records) - 1
    above_ma30 = ma30[li] and last['close'] > ma30[li]
    above_ma5  = ma5[li]  and last['close'] > ma5[li]
    bull_ma    = (ma5[li] and ma20[li] and ma60[li] and
                  ma5[li] > ma20[li] > ma60[li])
    prev_close = records[li-1]['close'] if li > 0 else None
    chg = (last['close'] - prev_close) / prev_close * 100 if prev_close else 0

    print()
    print(f'  当前收盘：{last["close"]:.2f}  较前日：{chg:+.2f}%')
    print(f'  MA5={ma5[li]:.2f}  MA10={ma10[li]:.2f}  MA20={ma20[li]:.2f}  MA30={ma30[li]:.2f}  MA60={ma60[li]:.2f}')
    print(f'  站上MA5：{"是" if above_ma5 else "否"}  站上MA30：{"是" if above_ma30 else "否"}  多头排列(MA5>MA20>MA60)：{"是" if bull_ma else "否"}')

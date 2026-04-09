import struct

def read_day_file(filepath):
    records = []
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32: break
                date, open_, high, low, close, amount, volume, reserved = struct.unpack('<IIIIIfII', chunk)
                records.append({'date':date,'open':open_/100.0,'high':high/100.0,'low':low/100.0,'close':close/100.0,'volume':volume})
    except: pass
    return records

def calc_ma(values, n):
    result = []
    for i in range(len(values)):
        result.append(round(sum(values[max(0,i-n+1):i+1])/min(i+1,n),2) if i>=n-1 else None)
    return result

stocks = [
    ('sz300476', r'D:\soft\new_tdx\vipdoc\sz\lday\sz300476.day'),
    ('sz300145', r'D:\soft\new_tdx\vipdoc\sz\lday\sz300145.day'),
]

for code, path in stocks:
    records = read_day_file(path)
    if not records:
        print(code + ': failed'); continue

    closes  = [r['close'] for r in records]
    volumes = [r['volume'] for r in records]
    ma30 = calc_ma(closes, 30)
    ma60 = calc_ma(closes, 60)

    avg_vol_60 = sum(volumes[-60:])/60
    avg_vol_20 = sum(volumes[-20:])/20

    # 找突破MA30的日期（最近180天内）
    bi = -1
    for i in range(max(1, len(records)-180), len(records)):
        if ma30[i] and ma30[i-1]:
            if records[i-1]['close'] <= ma30[i-1] and records[i]['close'] > ma30[i]:
                bi = i
    # 找最近180天最大量日期
    n180 = min(180, len(records))
    max_vol_idx = max(range(len(records)-n180, len(records)), key=lambda i: volumes[i])

    print()
    print('='*72)
    print('  %s' % code)
    print('='*72)
    last = records[-1]
    print('  当前: %.2f | MA30=%.2f MA60=%.2f' % (last['close'], ma30[-1] or 0, ma60[-1] or 0))
    print('  近20日均量/近60日均量 = %.2fx' % (avg_vol_20/avg_vol_60))
    d = str(records[max_vol_idx]['date'])
    print('  近180天最大单日量: %s 日期 %s-%s-%s' % (
        '{:,}'.format(volumes[max_vol_idx]), d[:4], d[4:6], d[6:]))
    if bi > 0:
        bd = str(records[bi]['date'])
        print('  突破MA30日: %s-%s-%s  收盘=%.2f (此为关键支撑位)' % (
            bd[:4], bd[4:6], bd[6:], records[bi]['close']))
        # 突破后最低回踩价
        post_low = min(r['close'] for r in records[bi:])
        post_low_date = ''
        for r in records[bi:]:
            if r['close'] == post_low:
                d2 = str(r['date'])
                post_low_date = '%s-%s-%s' % (d2[:4], d2[4:6], d2[6:])
                break
        print('  突破后最低回踩: %.2f (%s)  是否跌破突破日收盘: %s' % (
            post_low, post_low_date,
            '是 !!!' if post_low < records[bi]['close'] else '否（守住了）'))

    # 打印最近50天K线
    print()
    print('  最近50天K线:')
    print('  %-12s %7s %7s %7s %7s %7s %7s  %14s' % ('Date','Open','High','Low','Close','MA30','MA60','Volume'))
    for i in range(-50, 0):
        r = records[i]
        idx = len(records)+i
        d = str(r['date'])
        d_fmt = '%s-%s-%s' % (d[:4],d[4:6],d[6:])
        m30 = ('%.2f' % ma30[idx]) if ma30[idx] else '-'
        m60 = ('%.2f' % ma60[idx]) if ma60[idx] else '-'
        vol_ratio = volumes[idx]/avg_vol_60
        flag = ''
        # 突破标记
        if idx > 0 and ma30[idx] and ma30[idx-1]:
            if records[idx-1]['close'] <= ma30[idx-1] and r['close'] > ma30[idx]:
                flag = '<-- BREAK (%.2f)' % r['close']
        if ma30[idx] and r['close'] < ma30[idx]:
            flag = '[below MA30]'
        vol_tag = '  放%.1fx' % vol_ratio if vol_ratio >= 2.0 else ('  缩%.2fx' % vol_ratio if vol_ratio < 0.5 else '')
        print('  %-12s %7.2f %7.2f %7.2f %7.2f %7s %7s  %14s  %s%s' % (
            d_fmt, r['open'],r['high'],r['low'],r['close'],
            m30, m60, '{:,}'.format(r['volume']), flag, vol_tag))

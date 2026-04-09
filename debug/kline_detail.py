import struct

def read_day_file(filepath):
    records = []
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32:
                    break
                date, open_, high, low, close, amount, volume, reserved = struct.unpack('<IIIIIfII', chunk)
                records.append({'date': date, 'open': open_/100.0, 'high': high/100.0,
                                'low': low/100.0, 'close': close/100.0, 'volume': volume})
    except Exception as e:
        pass
    return records

def calc_ma(values, n):
    result = []
    for i in range(len(values)):
        if i < n-1:
            result.append(None)
        else:
            result.append(round(sum(values[i-n+1:i+1])/n, 2))
    return result

stocks = [
    ('sh603093', r'D:\soft\new_tdx\vipdoc\sh\lday\sh603093.day'),
    ('sh603538', r'D:\soft\new_tdx\vipdoc\sh\lday\sh603538.day'),
    ('sh601003', r'D:\soft\new_tdx\vipdoc\sh\lday\sh601003.day'),
    ('sz000953', r'D:\soft\new_tdx\vipdoc\sz\lday\sz000953.day'),
    ('sz300468', r'D:\soft\new_tdx\vipdoc\sz\lday\sz300468.day'),
]

for code, path in stocks:
    records = read_day_file(path)
    if not records:
        print(code + ': read failed')
        continue

    closes  = [r['close'] for r in records]
    volumes = [r['volume'] for r in records]
    ma5  = calc_ma(closes, 5)
    ma10 = calc_ma(closes, 10)
    ma20 = calc_ma(closes, 20)
    ma30 = calc_ma(closes, 30)
    ma60 = calc_ma(closes, 60)

    last = records[-1]
    print('\n' + '='*60)
    print('  ' + code)
    print('='*60)
    print('  Latest close : %.2f' % last['close'])
    print('  MA5=%.2f  MA10=%.2f  MA20=%.2f  MA30=%.2f  MA60=%.2f' % (
        ma5[-1] or 0, ma10[-1] or 0, ma20[-1] or 0, ma30[-1] or 0, ma60[-1] or 0))
    above_ma30 = last['close'] > (ma30[-1] or 0)
    above_ma60 = last['close'] > (ma60[-1] or 0)
    print('  Above MA30: %s  |  Above MA60: %s' % (above_ma30, above_ma60))

    avg_vol_60 = sum(volumes[-60:]) / 60
    avg_vol_20 = sum(volumes[-20:]) / 20
    avg_vol_5  = sum(volumes[-5:])  / 5
    print('  Vol ratio 5d/20d: %.2f  |  5d/60d: %.2f  (>1 expand <1 shrink)' % (
        avg_vol_5/avg_vol_20, avg_vol_5/avg_vol_60))

    # find peak (highest close in last 180 days)
    lookback = min(180, len(records))
    peak_idx = max(range(len(records)-lookback, len(records)), key=lambda i: records[i]['close'])
    peak_date = str(records[peak_idx]['date'])
    peak_price = records[peak_idx]['close']
    trough_after = min(records[peak_idx:], key=lambda r: r['close'])
    drop_pct = (peak_price - trough_after['close']) / peak_price * 100
    print('  Peak %.2f (%s-%s-%s) -> Low %.2f  Drop: %.1f%%' % (
        peak_price, peak_date[:4], peak_date[4:6], peak_date[6:],
        trough_after['close'], drop_pct))

    # recent 30 days detail
    print('\n  Last 30 days:')
    print('  %-12s %7s %7s %7s %7s %7s %12s' % ('Date','Open','High','Low','Close','MA30','Volume'))
    for i in range(-30, 0):
        r = records[i]
        idx = len(records) + i
        d = str(r['date'])
        d_fmt = '%s-%s-%s' % (d[:4], d[4:6], d[6:])
        m30 = ('%.2f' % ma30[idx]) if ma30[idx] else '-'
        # detect breakout
        flag = ''
        if idx > 0 and ma30[idx] and ma30[idx-1]:
            if records[idx-1]['close'] <= ma30[idx-1] and r['close'] > ma30[idx]:
                flag = '<-- BREAK'
        # detect drop below MA30
        if idx > 0 and ma30[idx] and r['close'] < ma30[idx]:
            flag = '  [below]'
        print('  %-12s %7.2f %7.2f %7.2f %7.2f %7s %12s %s' % (
            d_fmt, r['open'], r['high'], r['low'], r['close'], m30,
            '{:,}'.format(r['volume']), flag))

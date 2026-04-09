"""逐步追踪 002923 在新策略中被哪个条件过滤"""
import struct, sys
sys.stdout.reconfigure(encoding='utf-8')

SURGE_MIN_PCT     = 20.0
SURGE_MIN_DAYS    = 5
SURGE_MAX_DAYS    = 80
PULLBACK_MIN_PCT  = 5.0
PULLBACK_MAX_PCT  = 35.0
PULLBACK_MIN_DAYS = 8
PULLBACK_MAX_DAYS = 50
SHRINK_RATIO      = 0.80
RETRACE_MAX       = 0.618
MIN_PRICE         = 3.0

def read_day_file(filepath):
    records = []
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(32)
            if len(chunk) < 32: break
            date, open_, high, low, close, amount, volume, _ = struct.unpack('<IIIIIfII', chunk)
            records.append({'date': date, 'open': open_/100, 'high': high/100,
                             'low': low/100, 'close': close/100, 'volume': volume})
    return records

def calc_ma(values, n):
    return [None if i < n-1 else sum(values[i-n+1:i+1])/n for i in range(len(values))]

def fmt(d):
    s = str(d); return f'{s[:4]}-{s[4:6]}-{s[6:]}'

records = read_day_file(r'D:\soft\new_tdx\vipdoc\sz\lday\sz002923.day')
closes  = [r['close'] for r in records]
volumes = [r['volume'] for r in records]
ma30    = calc_ma(closes, 30)
ma5     = calc_ma(closes, 5)
ma20    = calc_ma(closes, 20)
ma60    = calc_ma(closes, 60)

break_start, break_end = 20260204, 20260312

print('=== 寻找突破日 ===')
bi = -1
for i in range(1, len(records)):
    date = records[i]['date']
    if date < break_start or date > break_end: continue
    if ma30[i] is None or ma30[i-1] is None: continue
    if not (records[i-1]['close'] <= ma30[i-1] and records[i]['close'] > ma30[i]): continue
    confirmed = False
    for j in range(i+1, min(i+4, len(records))):
        if ma30[j] and records[j]['close'] > ma30[j]:
            confirmed = True; break
    print(f'  候选突破日 {fmt(date)}: prev_close={records[i-1]["close"]:.2f} ma30_prev={ma30[i-1]:.2f} | close={records[i]["close"]:.2f} ma30={ma30[i]:.2f} | 确认={confirmed}')
    if confirmed:
        bi = i
        break

if bi < 0:
    print('  未找到突破日！')
    exit()

print(f'  → 突破日：{fmt(records[bi]["date"])}  收盘={records[bi]["close"]:.2f}  MA30={ma30[bi]:.2f}')
break_close = records[bi]['close']
break_ma30  = ma30[bi]
break_pct   = (break_close - break_ma30) / break_ma30 * 100
print(f'  超MA30：{break_pct:+.2f}%  (要求 0.3~15%)')

print('\n=== 寻找主升浪峰值 ===')
peak_search_start = max(0, bi - SURGE_MAX_DAYS - PULLBACK_MAX_DAYS)
peak_search_end   = bi - 2
peak_local = max(range(peak_search_end - peak_search_start + 1),
                 key=lambda k: closes[peak_search_start + k])
peak_idx   = peak_search_start + peak_local
peak_close = closes[peak_idx]
print(f'  峰值：{fmt(records[peak_idx]["date"])}  收盘={peak_close:.2f}')
print(f'  搜索范围：{fmt(records[peak_search_start]["date"])} ~ {fmt(records[peak_search_end]["date"])}')

print('\n=== 寻找回调低点 ===')
pb_slice  = closes[peak_idx + 1:bi]
pb_local  = min(range(len(pb_slice)), key=lambda k: pb_slice[k])
pb_idx    = peak_idx + 1 + pb_local
pb_close  = closes[pb_idx]
pullback_days = pb_idx - peak_idx
pb_pct    = (peak_close - pb_close) / peak_close * 100
print(f'  回调低点：{fmt(records[pb_idx]["date"])}  收盘={pb_close:.2f}')
print(f'  回调幅度：{pb_pct:.1f}%  (要求 {PULLBACK_MIN_PCT}~{PULLBACK_MAX_PCT}%)  → {"通过" if PULLBACK_MIN_PCT <= pb_pct <= PULLBACK_MAX_PCT else "❌过滤"}')
print(f'  回调天数：{pullback_days}天  (要求 {PULLBACK_MIN_DAYS}~{PULLBACK_MAX_DAYS}天)  → {"通过" if PULLBACK_MIN_DAYS <= pullback_days <= PULLBACK_MAX_DAYS else "❌过滤"}')

print('\n=== 寻找主升浪起点 ===')
base_search_start = max(0, peak_idx - SURGE_MAX_DAYS)
base_search_end   = max(0, peak_idx - SURGE_MIN_DAYS)
base_slice = closes[base_search_start:base_search_end + 1]
base_local = min(range(len(base_slice)), key=lambda k: base_slice[k])
base_idx   = base_search_start + base_local
base_close = closes[base_idx]
surge_pct  = (peak_close - base_close) / base_close * 100
surge_amplitude = peak_close - base_close
retraced        = peak_close - pb_close
retrace_ratio   = retraced / surge_amplitude if surge_amplitude > 0 else 1.0
print(f'  起点：{fmt(records[base_idx]["date"])}  收盘={base_close:.2f}')
print(f'  主升涨幅：{surge_pct:.1f}%  (要求 >={SURGE_MIN_PCT}%)  → {"通过" if surge_pct >= SURGE_MIN_PCT else "❌过滤"}')
print(f'  回调低点 vs 起点*1.10：{pb_close:.2f} vs {base_close*1.10:.2f}  → {"通过" if pb_close >= base_close*1.10 else "❌过滤"}')
print(f'  斐波回撤：{retrace_ratio*100:.1f}%  (要求 <{RETRACE_MAX*100:.1f}%)  → {"通过" if retrace_ratio <= RETRACE_MAX else "❌过滤"}')

print('\n=== 量能对比 ===')
surge_vols    = volumes[base_idx:peak_idx + 1]
pullback_vols = volumes[peak_idx + 1:pb_idx + 1]
avg_surge     = sum(surge_vols) / len(surge_vols)
avg_pb        = sum(pullback_vols) / len(pullback_vols)
shrink        = avg_pb / avg_surge
print(f'  主升均量：{avg_surge/10000:.0f}万手  回调均量：{avg_pb/10000:.0f}万手')
print(f'  缩量比：{shrink:.2f}x  (要求 <{SHRINK_RATIO})  → {"通过" if shrink <= SHRINK_RATIO else "❌过滤"}')

print('\n=== MA多头排列（突破日）===')
bull_ma = (ma5[bi] and ma20[bi] and ma60[bi] and ma5[bi] > ma20[bi] and ma20[bi] > ma60[bi])
print(f'  MA5={ma5[bi]:.2f}  MA20={ma20[bi]:.2f}  MA60={ma60[bi]:.2f}  多头排列：{bull_ma}')

print('\n=== 当前是否仍在MA30上方 ===')
last_close = records[-1]['close']
last_ma30  = ma30[-1]
print(f'  最新收盘={last_close:.2f}  MA30={last_ma30:.2f}  → {"通过" if last_close >= last_ma30 else "❌过滤（已跌破MA30）"}')

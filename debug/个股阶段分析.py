"""
个股阶段分析（与大盘阶段逻辑相同，参数针对个股调整）
用法: python 个股阶段分析.py sh603158
"""
import struct, os, sys

CODE = sys.argv[1] if len(sys.argv) > 1 else 'sh603158'
START_DATE = 20250101

DATA_DIRS = {
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
}

# 个股参数（比大盘阈值更宽松，因为个股波动更大）
MA30_SLOPE_DAYS  = 5      # 斜率回望天数
SLOPE_UP         = 0.3    # MA30斜率 > 0.3% 才算上升（大盘用0.05%）
SLOPE_DOWN       = -0.3   # MA30斜率 < -0.3% 才算下降
PRICE_STRONG_PCT = 2.0    # 价格高于MA30超过2%才算强势（大盘用1%）
PRICE_NEAR_PCT   = 3.0    # 价格在MA30±3%以内算贴近（大盘用2%）


def read_day_file(path):
    records = []
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32: break
                date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
                records.append({'date': date, 'open': o/100, 'high': h/100,
                                'low': l/100, 'close': c/100, 'volume': vol})
    except: pass
    return records


def calc_ma(values, n):
    r = [None] * len(values)
    for i in range(n - 1, len(values)):
        r[i] = sum(values[i - n + 1:i + 1]) / n
    return r


def fmt_date(d):
    d = str(d)
    return f'{d[:4]}-{d[4:6]}-{d[6:]}'


# ── 读取个股数据 ──────────────────────────────────────────────────────
market = CODE[:2]
path   = os.path.join(DATA_DIRS[market], f'{CODE}.day')
if not os.path.exists(path):
    print(f'找不到文件：{path}'); sys.exit(1)

all_recs = read_day_file(path)
closes   = [r['close'] for r in all_recs]
ma5      = calc_ma(closes, 5)
ma10     = calc_ma(closes, 10)
ma30     = calc_ma(closes, 30)

# ── 计算每天阶段 ──────────────────────────────────────────────────────
phases = []
for i, r in enumerate(all_recs):
    if r['date'] < START_DATE: continue
    if ma30[i] is None: continue

    c   = r['close']
    m30 = ma30[i]
    vs  = (c - m30) / m30 * 100

    if i >= MA30_SLOPE_DAYS and ma30[i - MA30_SLOPE_DAYS]:
        sl30 = (m30 - ma30[i - MA30_SLOPE_DAYS]) / ma30[i - MA30_SLOPE_DAYS] * 100
    else:
        sl30 = 0

    above   = c >= m30
    rising  = sl30 > SLOPE_UP
    falling = sl30 < SLOPE_DOWN
    strong  = vs > PRICE_STRONG_PCT
    near    = abs(vs) <= PRICE_NEAR_PCT

    if above and rising and strong:
        phase = '★做波段'
    elif above and not falling:
        phase = '△企稳观察'
    elif near and not falling:
        phase = '△企稳观察'
    else:
        phase = '▼空仓'

    pct = (c - all_recs[i-1]['close']) / all_recs[i-1]['close'] * 100 if i > 0 else 0

    phases.append({
        'date':  r['date'],
        'close': c,
        'ma30':  round(m30, 2),
        'vs':    round(vs, 2),
        'sl30':  round(sl30, 3),
        'phase': phase,
        'pct':   round(pct, 2),
        'vol':   r['volume'],
    })

# ── 合并连续阶段 ──────────────────────────────────────────────────────
segments = []
if phases:
    cur = {
        'phase': phases[0]['phase'],
        'start': phases[0]['date'], 'end': phases[0]['date'],
        'start_close': phases[0]['close'], 'end_close': phases[0]['close'],
        'days': 1,
        'rets': []
    }
    for p in phases[1:]:
        ret = p['pct']
        if p['phase'] == cur['phase']:
            cur['end']       = p['date']
            cur['end_close'] = p['close']
            cur['days']     += 1
            cur['rets'].append(ret)
        else:
            segments.append(cur)
            cur = {
                'phase': p['phase'],
                'start': p['date'], 'end': p['date'],
                'start_close': p['close'], 'end_close': p['close'],
                'days': 1, 'rets': [ret]
            }
    segments.append(cur)

# 合并相邻同阶段（短段<=2天合并）
merged = []
for seg in segments:
    if merged and merged[-1]['phase'] == seg['phase']:
        merged[-1]['end']       = seg['end']
        merged[-1]['end_close'] = seg['end_close']
        merged[-1]['days']     += seg['days']
        merged[-1]['rets']     += seg['rets']
    elif seg['days'] <= 2 and merged:
        # 短段并入前段
        merged[-1]['end']       = seg['end']
        merged[-1]['end_close'] = seg['end_close']
        merged[-1]['days']     += seg['days']
        merged[-1]['rets']     += seg['rets']
    else:
        merged.append(seg)

# 再合并一次相邻同阶段
final = []
for seg in merged:
    if final and final[-1]['phase'] == seg['phase']:
        final[-1]['end']       = seg['end']
        final[-1]['end_close'] = seg['end_close']
        final[-1]['days']     += seg['days']
        final[-1]['rets']     += seg['rets']
    else:
        final.append(seg)

# ── 输出阶段时间轴 ────────────────────────────────────────────────────
print('=' * 72)
print(f'【个股阶段分析】{CODE}  （2025-01至今）')
print(f'  参数：MA30斜率阈值±{SLOPE_UP}%  强势距离>{PRICE_STRONG_PCT}%  贴近范围±{PRICE_NEAR_PCT}%')
print('=' * 72)
print(f'  {"阶段":<8} {"开始":^12} {"结束":^12} {"天数":>5}  {"起点":>8} {"终点":>8} {"区间涨跌":>9}')
print('  ' + '─' * 66)

phase_stats = {'★做波段': {'days':0,'gain':0}, '△企稳观察': {'days':0,'gain':0}, '▼空仓': {'days':0,'gain':0}}

for seg in final:
    gain = (seg['end_close'] - seg['start_close']) / seg['start_close'] * 100
    tag  = '  '
    if abs(gain) >= 10: tag = '◎'
    elif abs(gain) >= 5: tag = '△'
    print(f'  {seg["phase"]:<7} {fmt_date(seg["start"]):^12} {fmt_date(seg["end"]):^12} '
          f'{seg["days"]:>5}天  {seg["start_close"]:>8.2f} {seg["end_close"]:>8.2f} '
          f'{gain:>+8.1f}% {tag}')
    ph = seg['phase']
    if ph in phase_stats:
        phase_stats[ph]['days'] += seg['days']
        phase_stats[ph]['gain'] += gain * seg['days']

# ── 统计 ──────────────────────────────────────────────────────────────
print()
print('─' * 72)
total_days = sum(v['days'] for v in phase_stats.values())
print(f'  统计期共 {total_days} 个交易日')
for ph in ['★做波段', '△企稳观察', '▼空仓']:
    d = phase_stats[ph]['days']
    avg_g = phase_stats[ph]['gain'] / d if d else 0
    print(f'  {ph}：{d:>4}天  占比{d/total_days*100:>5.1f}%  阶段内平均日收益{avg_g/d*100:>+.3f}%' if d else
          f'  {ph}：   0天')

# ── 转折点详情 ────────────────────────────────────────────────────────
print()
print('=' * 72)
print('【关键转折点】')
print('=' * 72)
prev = None
for p in phases:
    if p['phase'] != prev:
        arrow = {'★做波段': '→ 做波段  ★', '△企稳观察': '→ 企稳观察△', '▼空仓': '→ 空  仓  ▼'}[p['phase']]
        print(f'  {fmt_date(p["date"])}  {arrow}  '
              f'收{p["close"]:.2f}  MA30={p["ma30"]:.2f}  '
              f'离MA30={p["vs"]:>+.1f}%  斜率={p["sl30"]:>+.3f}%  当日{p["pct"]:>+.2f}%')
        prev = p['phase']

# ── 最新状态 ──────────────────────────────────────────────────────────
last = phases[-1]
print()
print('─' * 72)
print(f'  当前阶段：{last["phase"]}')
print(f'  最新收盘：{last["close"]:.2f}  MA30={last["ma30"]:.2f}  '
      f'离MA30={last["vs"]:>+.1f}%  MA30斜率={last["sl30"]:>+.3f}%')

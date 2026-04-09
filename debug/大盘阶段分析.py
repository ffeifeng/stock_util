"""
大盘阶段分析：2025-01 至 2026-03
基于沪指(sh000001)日线数据，统计：
  - 企稳阶段（何时开始、何时结束）
  - 适合做波段的时期
  - 适合空仓的时期
"""
import struct, os

if __import__('sys').stdout.__class__.__name__ != 'NoneType':
    try: __import__('sys').stdout.reconfigure(encoding='utf-8')
    except: pass

INDEX_FILE = r'D:\soft\new_tdx\vipdoc\sh\lday\sh000001.day'

START_DATE = 20250101
END_DATE   = 20261231   # 取到数据文件最新日期


def read_index(path):
    records = []
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(32)
            if len(chunk) < 32: break
            date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
            records.append({'date': date, 'open': o/100, 'high': h/100,
                            'low': l/100, 'close': c/100})
    return records


def calc_ma(values, n):
    r = [None] * len(values)
    for i in range(n - 1, len(values)):
        r[i] = sum(values[i - n + 1:i + 1]) / n
    return r


def slope(values, i, n=5):
    """计算MA的n日斜率（百分比变化）"""
    if i < n: return 0
    if values[i] is None or values[i - n] is None: return 0
    return (values[i] - values[i - n]) / values[i - n] * 100


def fmt_date(d):
    d = str(d)
    return f'{d[:4]}-{d[4:6]}-{d[6:]}'


# ── 读取数据 ──────────────────────────────────────────────────────────
all_records = read_index(INDEX_FILE)
closes = [r['close'] for r in all_records]
highs  = [r['high']  for r in all_records]
lows   = [r['low']   for r in all_records]

ma5  = calc_ma(closes, 5)
ma10 = calc_ma(closes, 10)
ma30 = calc_ma(closes, 30)
ma60 = calc_ma(closes, 60)

# 过滤到目标区间
records = [(all_records[i], ma5[i], ma10[i], ma30[i], ma60[i], i)
           for i in range(len(all_records))
           if START_DATE <= all_records[i]['date'] <= END_DATE
           and ma30[i] is not None]

# ── 判断每天的阶段 ──────────────────────────────────────────────────
# 阶段定义：
#   空仓：收盘 < MA30，MA30斜率为负
#   观察/企稳：收盘在MA30附近（±2%），或刚站上MA30，MA30斜率趋平
#   做波段：收盘 > MA30，MA30斜率为正，近期没有大幅回落

phases = []
for rec, m5, m10, m30, m60, idx in records:
    close = rec['close']
    date  = rec['date']

    vs_ma30 = (close - m30) / m30 * 100        # 收盘离MA30的距离%
    sl30    = slope(ma30, idx, 5)               # MA30近5日斜率
    sl10    = slope(ma10, idx, 5)               # MA10近5日斜率

    above_ma30 = close >= m30
    ma30_rising = sl30 > 0.05
    ma30_falling = sl30 < -0.05
    price_strong = vs_ma30 > 1.0               # 价格明显在MA30上方
    price_near   = abs(vs_ma30) <= 2.0         # 价格贴近MA30

    if above_ma30 and ma30_rising and price_strong:
        phase = '做波段'
    elif above_ma30 and not ma30_falling:
        phase = '企稳观察'
    elif price_near and not ma30_falling:
        phase = '企稳观察'
    else:
        phase = '空仓'

    phases.append({
        'date':     date,
        'close':    close,
        'ma30':     round(m30, 2),
        'vs_ma30':  round(vs_ma30, 2),
        'sl30':     round(sl30, 3),
        'phase':    phase,
    })

# ── 合并连续相同阶段 ──────────────────────────────────────────────────
segments = []
if phases:
    cur = {'phase': phases[0]['phase'], 'start': phases[0]['date'],
           'end': phases[0]['date'], 'days': 1,
           'start_close': phases[0]['close'], 'end_close': phases[0]['close']}
    for p in phases[1:]:
        if p['phase'] == cur['phase']:
            cur['end']       = p['date']
            cur['end_close'] = p['close']
            cur['days']     += 1
        else:
            segments.append(cur)
            cur = {'phase': p['phase'], 'start': p['date'],
                   'end': p['date'], 'days': 1,
                   'start_close': p['close'], 'end_close': p['close']}
    segments.append(cur)

# 合并相邻同类型短段（3天以内的过渡段合并到前一段）
merged = []
for seg in segments:
    if merged and seg['days'] <= 3 and merged[-1]['phase'] == phases[
            next((i for i, p in enumerate(phases) if p['date'] == seg['end']), -1)
            - seg['days']]['phase'] if merged else False:
        merged[-1]['end']       = seg['end']
        merged[-1]['end_close'] = seg['end_close']
        merged[-1]['days']     += seg['days']
    else:
        merged.append(seg)

# 再做一次合并：相邻且同phase的段合并
final = []
for seg in merged:
    if final and final[-1]['phase'] == seg['phase']:
        final[-1]['end']       = seg['end']
        final[-1]['end_close'] = seg['end_close']
        final[-1]['days']     += seg['days']
    else:
        final.append(seg)

# ── 输出 ──────────────────────────────────────────────────────────────
print('=' * 75)
print('【沪指阶段分析】2025-01 至 2026-03')
print('=' * 75)
print(f'  {"阶段":<6}  {"开始日期":^12} {"结束日期":^12} {"天数":>5}  {"起点":>8} {"终点":>8} {"涨跌":>8}')
print('  ' + '─' * 71)

phase_stats = {'做波段': 0, '企稳观察': 0, '空仓': 0}

for seg in final:
    pct = (seg['end_close'] - seg['start_close']) / seg['start_close'] * 100
    tag = {'做波段': '★', '企稳观察': '△', '空仓': '▼'}[seg['phase']]
    print(f'  {tag} {seg["phase"]:<5}  {fmt_date(seg["start"]):^12} {fmt_date(seg["end"]):^12} '
          f'{seg["days"]:>5}天  {seg["start_close"]:>8.2f} {seg["end_close"]:>8.2f} '
          f'{pct:>+7.1f}%')
    phase_stats[seg['phase']] += seg['days']

print()
print('─' * 75)
total = sum(phase_stats.values())
print(f'  统计期总交易日：{total} 天')
for ph, days in phase_stats.items():
    tag = {'做波段': '★', '企稳观察': '△', '空仓': '▼'}[ph]
    print(f'  {tag} {ph}：{days:>4} 天  占比 {days/total*100:.1f}%')
print()

# ── 逐日明细（只打印关键转折点）──────────────────────────────────────
print('=' * 75)
print('【关键转折点（阶段切换）】')
print('=' * 75)
prev_phase = None
for p in phases:
    if p['phase'] != prev_phase:
        arrow = {'做波段': '→ 做波段  ★', '企稳观察': '→ 企稳观察△', '空仓': '→ 空  仓  ▼'}[p['phase']]
        print(f'  {fmt_date(p["date"])}  {arrow}  '
              f'指数{p["close"]:.2f}  MA30={p["ma30"]:.2f}  '
              f'离MA30={p["vs_ma30"]:+.1f}%  MA30斜率={p["sl30"]:+.3f}')
        prev_phase = p['phase']

print()
print('  图例：★做波段=收盘>MA30且MA30向上  △企稳观察=贴近MA30或站上但未确认  ▼空仓=跌破MA30且MA30向下')

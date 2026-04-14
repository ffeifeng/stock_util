"""
大盘阶段分析：2025-01 至今
基于沪指(sh000001)日线数据，统计：
  - 企稳阶段（何时开始、何时结束）
  - 适合做波段的时期
  - 适合空仓的时期
"""
import struct, os, webbrowser

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


# ── 生成 HTML 时间轴 ──────────────────────────────────────────────────

def get_action(seg, is_last=False):
    phase = seg['phase']
    pct   = (seg['end_close'] - seg['start_close']) / seg['start_close'] * 100
    start_month = int(str(seg['start'])[4:6])
    if phase == '空仓':
        return '现在空仓' if is_last else '不操作'
    elif phase == '做波段':
        if pct > 10:   return '全年最佳'
        if start_month == 1 and pct > 1.5: return '年初行情'
        if pct > 2:    return '可做'
        return '谨慎'
    else:  # 企稳观察
        if pct < -1.5: return '观望'
        # 高位整理：前一段是大涨做波段
        idx = final.index(seg)
        if idx > 0 and final[idx-1]['phase'] == '做波段':
            prev_pct = (final[idx-1]['end_close'] - final[idx-1]['start_close']) / final[idx-1]['start_close'] * 100
            if prev_pct > 8: return '持仓'
        return '轻仓'

def get_change_desc(seg, is_last=False):
    pct  = (seg['end_close'] - seg['start_close']) / seg['start_close'] * 100
    sc   = int(seg['start_close'])
    ec   = int(seg['end_close'])
    sign = '+' if pct >= 0 else ''
    if seg['phase'] == '企稳观察':
        if abs(pct) < 1.5: return '小幅震荡'
        if pct < -1.5:     return '震荡下行'
        if seg['days'] <= 8: return '过渡'
        return '高位整理'
    if seg['phase'] == '做波段' and abs(pct) < 1.5:
        return '反复震荡'
    end_label = '至今' if is_last else str(ec)
    return f'{sc} → {end_label}<br><small>({sign}{pct:.1f}%)</small>'

last_date_str = fmt_date(phases[-1]['date'])
first_date_str = fmt_date(phases[0]['date'])

rows_html = ''
PHASE_STYLE = {
    '做波段':  ('★ 做波段',  '#27ae60', '#1e8449'),
    '企稳观察': ('△ 企稳观察', '#e67e22', '#ca6f1e'),
    '空仓':    ('▼ 空仓',    '#c0392b', '#a93226'),
}
ACTION_COLOR = {
    '全年最佳': '#f1c40f', '年初行情': '#2ecc71', '可做': '#2ecc71',
    '谨慎': '#e67e22', '轻仓': '#e67e22', '持仓': '#3498db',
    '观望': '#95a5a6', '不操作': '#7f8c8d', '现在空仓': '#e74c3c',
    '过渡': '#e67e22',
}

for i, seg in enumerate(final):
    is_last = (i == len(final) - 1)
    label, bg, bg2 = PHASE_STYLE[seg['phase']]
    pct  = (seg['end_close'] - seg['start_close']) / seg['start_close'] * 100
    action = get_action(seg, is_last)
    change = get_change_desc(seg, is_last)
    act_color = ACTION_COLOR.get(action, '#95a5a6')
    end_disp = '至今' if is_last else fmt_date(seg['end'])
    days_disp = f'{seg["days"]}天{"+" if is_last else ""}'
    rows_html += f'''
    <tr>
      <td><span class="phase-badge" style="background:{bg};border-left:4px solid {bg2}">{label}</span></td>
      <td class="date-cell">{fmt_date(seg["start"])} → {end_disp}</td>
      <td class="days-cell">{days_disp}</td>
      <td class="change-cell">{change}</td>
      <td><span class="action-badge" style="background:{act_color}22;color:{act_color};border:1px solid {act_color}55">{action}</span></td>
    </tr>'''

html = f'''<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>大盘阶段时间轴</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f0f1a;color:#e0e0e0;font-family:"Microsoft YaHei",sans-serif;padding:24px}}
  h2{{color:#a0c4ff;font-size:1.1rem;margin-bottom:16px;letter-spacing:1px}}
  table{{width:100%;border-collapse:collapse;font-size:0.88rem}}
  th{{background:#1a1a2e;color:#8899bb;font-weight:500;padding:10px 14px;text-align:left;
      border-bottom:1px solid #2a2a4a;letter-spacing:0.5px}}
  td{{padding:10px 14px;border-bottom:1px solid #1e1e32;vertical-align:middle}}
  tr:hover td{{background:#1a1a30}}
  .phase-badge{{display:inline-block;padding:3px 10px;border-radius:4px;font-size:0.82rem;
               font-weight:600;color:#fff;letter-spacing:0.5px}}
  .action-badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:0.82rem;font-weight:600}}
  .date-cell{{color:#aabbdd;font-size:0.83rem;letter-spacing:0.3px}}
  .days-cell{{color:#6699cc;font-weight:600;text-align:center}}
  .change-cell{{color:#ccd6e0;font-size:0.83rem;line-height:1.5}}
  .change-cell small{{color:#7788aa;font-size:0.78rem}}
  .stats{{margin-top:18px;display:flex;gap:24px;font-size:0.82rem;color:#7799aa}}
  .stats span{{background:#1a1a2e;padding:6px 14px;border-radius:6px}}
</style></head><body>
<h2>完整阶段时间轴（{first_date_str[:7].replace("-","年",1).replace("-","月")} ～ {last_date_str}）</h2>
<table>
  <thead><tr>
    <th>阶段</th><th>时间段</th><th style="text-align:center">天数</th>
    <th>指数变化</th><th>操作</th>
  </tr></thead>
  <tbody>{rows_html}
  </tbody>
</table>
<div class="stats">
  <span>★ 做波段：{phase_stats["做波段"]}天 ({phase_stats["做波段"]/sum(phase_stats.values())*100:.0f}%)</span>
  <span>△ 企稳观察：{phase_stats["企稳观察"]}天 ({phase_stats["企稳观察"]/sum(phase_stats.values())*100:.0f}%)</span>
  <span>▼ 空仓：{phase_stats["空仓"]}天 ({phase_stats["空仓"]/sum(phase_stats.values())*100:.0f}%)</span>
</div>
</body></html>'''

out_path = os.path.join(os.path.dirname(__file__), '..', 'output', '大盘阶段时间轴.html')
out_path = os.path.normpath(out_path)
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'\n  HTML → {out_path}')
webbrowser.open('file:///' + out_path.replace('\\', '/'))

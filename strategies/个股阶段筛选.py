"""
个股阶段筛选：从今日MA30扫描A组中，按大盘阶段逻辑
筛选出"可介入波段"和"企稳观察"两类个股
判断标准（与大盘阶段逻辑一致）：
  做波段：收盘 > MA30 AND MA30斜率 > 0.05 AND 收盘离MA30 > 1%
  企稳观察：收盘 > MA30 AND MA30斜率未明显下行（-0.05以上）
"""
import struct, os, sys, json
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

DATA_DIRS = {
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
}

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output', '均线策略')
DB_PATH  = os.path.join(OUT_DIR, 'MA30扫描_数据库.json')
OUT_DIR2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output', '个股阶段')
os.makedirs(OUT_DIR2, exist_ok=True)

ts = datetime.now().strftime('%Y%m%d')


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


def ma_slope(ma_list, i, n=5):
    """MA近n日斜率（%）"""
    if i < n or ma_list[i] is None or ma_list[i - n] is None: return 0
    return (ma_list[i] - ma_list[i - n]) / ma_list[i - n] * 100


def get_stock_file(code):
    market = code[:2]
    num    = code[2:]
    return os.path.join(DATA_DIRS.get(market, ''), f'{code}.day')


# ── 读取A组股票列表 ────────────────────────────────────────────────
if not os.path.exists(DB_PATH):
    print(f'数据库文件不存在：{DB_PATH}')
    sys.exit(1)

with open(DB_PATH, 'r', encoding='utf-8') as f:
    db = json.load(f)

# A组：在MA30上方整理的股票
stocks = db.get('stocks', db)
a_group = {code: info for code, info in stocks.items() if info.get('last_group') == 'A'}
print(f'A组共 {len(a_group)} 只，逐一分析阶段...')

wave_list   = []   # 可介入波段
watch_list  = []   # 企稳观察（站上但未确认）

for code, info in a_group.items():
    path = get_stock_file(code)
    if not os.path.exists(path): continue

    records = read_day_file(path)
    if len(records) < 40: continue

    closes  = [r['close'] for r in records]
    volumes = [r['volume'] for r in records]
    ma5     = calc_ma(closes, 5)
    ma10    = calc_ma(closes, 10)
    ma20    = calc_ma(closes, 20)
    ma30    = calc_ma(closes, 30)
    ma60    = calc_ma(closes, 60)

    idx   = len(records) - 1
    close = closes[idx]
    m30   = ma30[idx]
    m5    = ma5[idx]
    m10   = ma10[idx]
    m60   = ma60[idx]

    if m30 is None or close < m30: continue

    sl30     = ma_slope(ma30, idx, 5)
    vs_ma30  = (close - m30) / m30 * 100

    # 连续在MA30上方天数
    days_above = 0
    for k in range(idx, max(idx - 30, -1), -1):
        if ma30[k] and records[k]['close'] >= ma30[k]:
            days_above += 1
        else:
            break

    # MA多头排列：MA5 > MA10 > MA60
    bull_ma = (m5 and m10 and m60 and m5 > m10 and m10 > m60)

    # 近5日均量 vs 近20日均量（是否放量）
    vol_ma5  = sum(volumes[idx - 4:idx + 1]) / 5  if idx >= 4  else 0
    vol_ma20 = sum(volumes[idx - 19:idx + 1]) / 20 if idx >= 19 else 0
    vol_ratio = round(vol_ma5 / vol_ma20, 2) if vol_ma20 > 0 else 0

    item = {
        'code':       code,
        'close':      round(close, 2),
        'ma30':       round(m30, 2),
        'vs_ma30':    round(vs_ma30, 2),
        'sl30':       round(sl30, 3),
        'days_above': days_above,
        'bull_ma':    bull_ma,
        'vol_ratio':  vol_ratio,
        'change_pct': round(info.get('day_pct', 0), 2),
    }

    # 判断阶段
    ma30_rising  = sl30 > 0.05
    ma30_falling = sl30 < -0.05
    price_strong = vs_ma30 > 1.0

    if ma30_rising and price_strong:
        wave_list.append(item)
    elif not ma30_falling:
        watch_list.append(item)

# ── 排序 ──────────────────────────────────────────────────────────
# 做波段：MA30斜率降序 + 多头排列优先
wave_list.sort(key=lambda x: (not x['bull_ma'], -x['sl30'], -x['vs_ma30']))
# 企稳观察：离MA30从近到远，连续上方天数多的优先
watch_list.sort(key=lambda x: (-x['days_above'], x['vs_ma30']))


# ── 输出函数 ──────────────────────────────────────────────────────
def write_output(title, items, filepath, phase_label, today):
    lines = []
    def out(s=''):
        lines.append(s); print(s)

    out('=' * 82)
    out(f'【{title}】  数据日期：{today}  共 {len(items)} 只')
    if phase_label == 'wave':
        out('条件：收盘>MA30 且 MA30斜率>0.05% 且 收盘偏离MA30>1%')
    else:
        out('条件：收盘>MA30 且 MA30斜率未明显下行（即斜率>-0.05%），但未达到做波段标准')
    out('=' * 82)
    out(f'  {"排":>3}  {"代码":<10} {"收盘":>8} {"MA30":>8} {"离MA30":>7} '
        f'{"MA30斜率":>8} {"上方天":>6} {"量比":>5} {"多头":>4}  {"涨跌%":>6}')
    out('  ' + '─' * 78)

    for i, r in enumerate(items, 1):
        bull = '★' if r['bull_ma'] else ' '
        out(f'  {i:>3}  {r["code"]:<10} {r["close"]:>8.2f} {r["ma30"]:>8.2f} '
            f'{r["vs_ma30"]:>+6.1f}% {r["sl30"]:>+8.3f}  '
            f'{r["days_above"]:>5}天 {r["vol_ratio"]:>5.2f}x {bull:>4}  '
            f'{r["change_pct"]:>+5.1f}%')

    out()
    if phase_label == 'wave':
        out('  ★=MA多头排列（MA5>MA10>MA60）  MA30斜率>0代表均线向上  离MA30>1%说明站稳有力度')
    else:
        out('  上方天=连续收在MA30上方天数  MA30斜率接近0=均线趋平，等待方向确认')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'\n结果已保存：{filepath}')


# 获取今天日期
sample_records = read_day_file(get_stock_file(list(a_group.keys())[0]))
today_str = str(sample_records[-1]['date']) if sample_records else ts
today_fmt = f'{today_str[:4]}-{today_str[4:6]}-{today_str[6:]}'

wave_path  = os.path.join(OUT_DIR2, f'可介入波段_{ts}.txt')
watch_path = os.path.join(OUT_DIR2, f'企稳观察_{ts}.txt')

print()
write_output('可介入波段个股', wave_list, wave_path, 'wave', today_fmt)
print()
write_output('企稳观察个股（站上MA30但未确认趋势）', watch_list, watch_path, 'watch', today_fmt)

print(f'\n汇总：可介入波段 {len(wave_list)} 只  |  企稳观察 {len(watch_list)} 只')

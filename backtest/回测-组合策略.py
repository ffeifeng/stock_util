"""
组合策略回测：大盘阶段 × MA30站回 × 大涨过滤

三层过滤：
  ① 大盘阶段过滤：只在大盘"做波段"阶段才允许入场
     - 沪指收盘 > MA30，且 MA30 斜率 > +0.05%，且价格高于MA30超1%
  ② MA30站回信号：
     - 前天在MA30上方 → 昨天跌破 → 今天站回（离MA30≤3%）
  ③ 大涨过滤：近44交易日内至少有一天涨幅 >= 6%

买入：信号日收盘价
持有：1 / 3 / 5 天，计算胜率和平均收益

统计期：2025-01-01 至 2026-03-31
对比：同期 无大盘过滤（仅②③）的表现

用法：
  python 回测-组合策略.py
"""
import struct, os, sys
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

DATA_DIRS = {
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
}
INDEX_FILE  = r'D:\soft\new_tdx\vipdoc\sh\lday\sh000001.day'
MIN_PRICE   = 3.0
ABOVE_MAX   = 3.0    # 站回后距MA30不超过%
HOLD_DAYS   = 5      # 最长持有天数
SURGE_DAYS  = 44     # 近期大涨回望天数
SURGE_MIN   = 6.0    # 近期大涨最小涨幅%
MA30_SLOPE_DAYS = 5  # 计算MA30斜率的天数

START_DATE = 20250101
END_DATE   = 20260331

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, '回测-组合策略_202501_202603.txt')


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
    for i in range(n-1, len(values)):
        r[i] = sum(values[i-n+1:i+1]) / n
    return r


def is_valid_stock(code):
    c = code.lower()
    if c.startswith('bj'): return False
    num = c[2:]
    if num.startswith('688'): return False   # 排除科创板
    if c.startswith('sh'): return num[:3] in ['600','601','602','603','604','605']
    if c.startswith('sz'): return num[:3] in ['000','001','002','003','300','301']
    return False


def load_st_codes():
    st_set = set()
    p = r'D:\soft\st_codes.txt'
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                c = line.strip()
                if c: st_set.add(c)
    return st_set


def build_market_phase(index_file):
    """
    返回 {date: phase}
    phase: 'wave'=做波段, 'watch'=企稳观察, 'cash'=空仓
    同时返回 {date: index_pct}
    """
    recs = read_day_file(index_file)
    closes = [r['close'] for r in recs]
    ma30   = calc_ma(closes, 30)
    phase_map = {}
    pct_map   = {}

    for i in range(len(recs)):
        d = recs[i]['date']
        if ma30[i] is None: continue
        c   = recs[i]['close']
        m30 = ma30[i]
        # 斜率
        if i >= MA30_SLOPE_DAYS and ma30[i - MA30_SLOPE_DAYS] is not None:
            sl30 = (m30 - ma30[i - MA30_SLOPE_DAYS]) / ma30[i - MA30_SLOPE_DAYS] * 100
        else:
            sl30 = 0
        vs = (c - m30) / m30 * 100
        above = c >= m30
        rising  = sl30 > 0.05
        falling = sl30 < -0.05

        if above and rising and vs > 1.0:
            phase_map[d] = 'wave'
        elif above and not falling:
            phase_map[d] = 'watch'
        elif abs(vs) <= 2.0 and not falling:
            phase_map[d] = 'watch'
        else:
            phase_map[d] = 'cash'

        if i > 0:
            pct_map[d] = (c - recs[i-1]['close']) / recs[i-1]['close'] * 100
        else:
            pct_map[d] = 0

    return phase_map, pct_map


def winrate(lst):
    if not lst: return 0
    return sum(1 for x in lst if x > 0) / len(lst) * 100


def avg(lst):
    if not lst: return 0
    return sum(lst) / len(lst)


def fmt(v): return f'{v:+.2f}%'


# ══════════════════════════════════════════════════════════════════════
def run():
    st_codes = load_st_codes()
    phase_map, pct_map = build_market_phase(INDEX_FILE)

    # 按组分类的信号收益
    # combo = 三层全过滤，base = 仅②③（无大盘过滤）
    combo_rets = defaultdict(list)   # {hold_days: [ret, ...]}
    base_rets  = defaultdict(list)

    # 按大盘阶段统计combo信号分布
    phase_cnt = defaultdict(int)

    # 按月统计
    monthly_combo = defaultdict(lambda: defaultdict(list))
    monthly_base  = defaultdict(lambda: defaultdict(list))

    total_stocks  = 0
    skip_no_data  = 0

    print('正在扫描...', flush=True)

    for market, data_dir in DATA_DIRS.items():
        if not os.path.exists(data_dir): continue
        for fname in sorted(os.listdir(data_dir)):
            if not fname.endswith('.day'): continue
            code = fname[:-4]
            if not is_valid_stock(code): continue
            if code[2:] in st_codes: continue

            records = read_day_file(os.path.join(data_dir, fname))
            if len(records) < SURGE_DAYS + HOLD_DAYS + 5: continue

            closes = [r['close'] for r in records]
            ma30   = calc_ma(closes, 30)
            total_stocks += 1

            for i in range(SURGE_DAYS + 2, len(records) - HOLD_DAYS):
                today = records[i]
                if not (START_DATE <= today['date'] <= END_DATE): continue
                if today['close'] < MIN_PRICE: continue
                if ma30[i] is None or ma30[i-1] is None or ma30[i-2] is None: continue

                # ── ② MA30站回信号 ──────────────────────────────────
                yest = records[i-1]
                day2 = records[i-2]
                today_above = today['close'] >= ma30[i]
                yest_above  = yest['close']  >= ma30[i-1]
                day2_above  = day2['close']  >= ma30[i-2]

                if not (today_above and not yest_above and day2_above):
                    continue
                above_pct = (today['close'] - ma30[i]) / ma30[i] * 100
                if above_pct > ABOVE_MAX:
                    continue

                # ── ③ 大涨过滤 ─────────────────────────────────────
                has_surge = False
                for k in range(i - SURGE_DAYS, i):
                    if k <= 0: continue
                    prev_c = records[k-1]['close']
                    if prev_c > 0:
                        pct = (records[k]['close'] - prev_c) / prev_c * 100
                        if pct >= SURGE_MIN:
                            has_surge = True
                            break
                if not has_surge:
                    continue

                # ── 计算持有收益 ────────────────────────────────────
                buy_price = today['close']
                rets = {}
                valid = True
                for d in range(1, HOLD_DAYS + 1):
                    if i + d >= len(records):
                        valid = False; break
                    rets[d] = (records[i+d]['close'] - buy_price) / buy_price * 100
                if not valid: continue

                month_tag = str(today['date'])[:6]

                # 基础版（无大盘过滤）
                for d in range(1, HOLD_DAYS + 1):
                    base_rets[d].append(rets[d])
                    monthly_base[month_tag][d].append(rets[d])

                # 组合版（加大盘阶段过滤）
                mkt_phase = phase_map.get(today['date'], 'cash')
                phase_cnt[mkt_phase] += 1
                if mkt_phase == 'wave':
                    for d in range(1, HOLD_DAYS + 1):
                        combo_rets[d].append(rets[d])
                        monthly_combo[month_tag][d].append(rets[d])

    # ══════════════════════════════════════════════════════════════════
    lines = []
    def out(s=''):
        lines.append(s); print(s)

    out('=' * 72)
    out('【组合策略回测】2025-01 至 2026-03')
    out('  策略：大盘做波段阶段 × MA30站回 × 近44日有≥6%大涨')
    out('=' * 72)
    out()

    # ── 大盘阶段分布 ─────────────────────────────────────────────────
    total_sig = sum(phase_cnt.values())
    out('【信号落在大盘各阶段的分布】')
    out(f'  基础版（②③）总信号数：{total_sig} 笔')
    for ph, label in [('wave','★做波段'),('watch','△企稳观察'),('cash','▼空仓')]:
        cnt = phase_cnt.get(ph, 0)
        pct = cnt / total_sig * 100 if total_sig else 0
        out(f'    {label}：{cnt:>4} 笔  占比 {pct:.1f}%')
    out()

    # ── 整体胜率对比 ─────────────────────────────────────────────────
    out('【整体胜率 & 平均收益对比】')
    out(f'  {"":12} {"持1天":>10} {"持3天":>10} {"持5天":>10}')
    out('  ' + '─' * 44)

    # 基础版
    b1 = base_rets[1]; b3 = base_rets[3]; b5 = base_rets[5]
    out(f'  {"基础版(无过滤)":<12} '
        f'{winrate(b1):>5.1f}%/{avg(b1):>+5.2f}%  '
        f'{winrate(b3):>5.1f}%/{avg(b3):>+5.2f}%  '
        f'{winrate(b5):>5.1f}%/{avg(b5):>+5.2f}%  '
        f'({len(b1)}笔)')

    # 组合版
    c1 = combo_rets[1]; c3 = combo_rets[3]; c5 = combo_rets[5]
    out(f'  {"组合版(做波段)":<12} '
        f'{winrate(c1):>5.1f}%/{avg(c1):>+5.2f}%  '
        f'{winrate(c3):>5.1f}%/{avg(c3):>+5.2f}%  '
        f'{winrate(c5):>5.1f}%/{avg(c5):>+5.2f}%  '
        f'({len(c1)}笔)')
    out()

    # ── 按月明细 ─────────────────────────────────────────────────────
    out('【按月明细（组合版 vs 基础版）胜率/均收益】')
    out(f'  {"月份":<8}  {"大盘阶段":^8}  '
        f'{"--- 组合版 ---":^34}  {"--- 基础版 ---":^34}')
    out(f'  {"":8}  {"":8}  '
        f'{"持1天":>10} {"持3天":>10} {"持5天":>10}  '
        f'{"持1天":>10} {"持3天":>10} {"持5天":>10}')
    out('  ' + '─' * 90)

    # 大盘各月主阶段
    month_phase = {}
    for d, ph in phase_map.items():
        if START_DATE <= d <= END_DATE:
            m = str(d)[:6]
            if m not in month_phase:
                month_phase[m] = defaultdict(int)
            month_phase[m][ph] += 1

    def main_phase(m):
        if m not in month_phase: return '?'
        mp = month_phase[m]
        dom = max(mp, key=mp.get)
        return {'wave': '★做波段', 'watch': '△观察', 'cash': '▼空仓'}[dom]

    for month in sorted(set(list(monthly_combo.keys()) + list(monthly_base.keys()))):
        cr = monthly_combo.get(month, {})
        br = monthly_base.get(month, {})
        c1m = cr.get(1, []); c3m = cr.get(3, []); c5m = cr.get(5, [])
        b1m = br.get(1, []); b3m = br.get(3, []); b5m = br.get(5, [])

        def fs(lst):
            if not lst: return '   -      '
            return f'{winrate(lst):>4.0f}%/{avg(lst):>+5.2f}%'

        ph_label = main_phase(month)
        out(f'  {month:<8}  {ph_label:<8}  '
            f'{fs(c1m):>10} {fs(c3m):>10} {fs(c5m):>10}  '
            f'{fs(b1m):>10} {fs(b3m):>10} {fs(b5m):>10}')

    out()
    out('  说明：胜率/均收益  例：62%/+1.23% 表示胜率62%，平均持仓收益+1.23%')
    out(f'  文件：{OUT_PATH}')

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'\n回测完成，结果已保存至：{OUT_PATH}')


if __name__ == '__main__':
    run()

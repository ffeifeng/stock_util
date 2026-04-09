"""
回测策略：站回MA30
  信号条件：
    - 前天收盘在MA30上方
    - 昨天收盘跌破MA30
    - 今天收盘站回MA30上方，且离MA30不超过 ABOVE_MAX%
  买入：信号日收盘价
  持有：1/2/3天，分别计算收益率和胜率

用法：
  python 回测-站回MA30.py                     # 默认回测2026年1月
  python 回测-站回MA30.py 20260101 20260131   # 指定起止日期
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
MIN_PRICE    = 3.0
ABOVE_MAX    = 3.0    # 站回MA30后距MA30不超过3%
HOLD_DAYS    = 3      # 最长持有天数
SURGE_DAYS   = 44     # 近两个月（约44交易日）
SURGE_MIN    = 6.0    # 近两个月内至少有一天涨幅超过该值（%）

# 回测区间（从命令行读，默认2026年1月）
START_DATE = int(sys.argv[1]) if len(sys.argv) > 2 else 20260101
END_DATE   = int(sys.argv[2]) if len(sys.argv) > 2 else 20260131

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, f'回测-站回MA30_含大涨过滤_{START_DATE}_{END_DATE}.txt')


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
    if c.startswith('sh'): return num[:3] in ['600','601','602','603','604','605','688']
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


def run():
    st_codes = load_st_codes()

    # signals[day_offset] = list of {code, buy_price, returns[1..3]}
    all_signals = []   # list of {date, code, buy_price, ret1, ret2, ret3}
    # 按持有天数分桶统计
    stats = {d: {'returns': [], 'wins': 0, 'total': 0} for d in range(1, HOLD_DAYS+1)}

    total_stocks = 0
    for market, data_dir in DATA_DIRS.items():
        if not os.path.exists(data_dir): continue
        for fname in os.listdir(data_dir):
            if not fname.endswith('.day'): continue
            code = fname[:-4]
            if not is_valid_stock(code): continue
            if code[2:] in st_codes: continue

            records = read_day_file(os.path.join(data_dir, fname))
            if len(records) < 35 + HOLD_DAYS: continue

            closes = [r['close'] for r in records]
            ma30 = calc_ma(closes, 30)

            total_stocks += 1

            # 遍历回测区间内的每一天
            for i in range(2, len(records) - HOLD_DAYS):
                today = records[i]
                if today['date'] < START_DATE or today['date'] > END_DATE:
                    continue
                if today['close'] < MIN_PRICE:
                    continue
                if ma30[i] is None or ma30[i-1] is None or ma30[i-2] is None:
                    continue

                yest    = records[i-1]
                day2ago = records[i-2]

                today_above  = today['close']  >= ma30[i]
                yest_above   = yest['close']   >= ma30[i-1]
                day2_above   = day2ago['close'] >= ma30[i-2]

                # 信号：前天上方 → 昨天跌破 → 今天站回，且离MA30不超过ABOVE_MAX%
                if not (day2_above and not yest_above and today_above):
                    continue
                above_pct = (today['close'] - ma30[i]) / ma30[i] * 100
                if above_pct > ABOVE_MAX:
                    continue

                # 近两个月内至少有一天涨幅超过SURGE_MIN%
                start_j = max(1, i - SURGE_DAYS)
                has_surge = any(
                    (records[j]['close'] - records[j-1]['close']) / records[j-1]['close'] * 100 >= SURGE_MIN
                    for j in range(start_j, i + 1)
                )
                if not has_surge:
                    continue

                buy_price = today['close']
                rets = {}
                for d in range(1, HOLD_DAYS + 1):
                    future_close = records[i + d]['close']
                    rets[d] = (future_close - buy_price) / buy_price * 100

                all_signals.append({
                    'date':      today['date'],
                    'code':      code,
                    'buy':       round(buy_price, 2),
                    'ma30':      round(ma30[i], 2),
                    'above_pct': round(above_pct, 2),
                    'ret1':      round(rets[1], 2),
                    'ret2':      round(rets[2], 2),
                    'ret3':      round(rets[3], 2),
                })
                for d in range(1, HOLD_DAYS + 1):
                    stats[d]['returns'].append(rets[d])
                    stats[d]['total']   += 1
                    if rets[d] > 0:
                        stats[d]['wins'] += 1

    # 按日期、代码排序
    all_signals.sort(key=lambda x: (x['date'], x['code']))

    # ── 输出 ────────────────────────────────────────────────────────
    lines = []
    def out(s=''):
        lines.append(s); print(s)

    out('=' * 80)
    out(f'  回测策略：站回MA30（离MA30≤{ABOVE_MAX}%）+ 近{SURGE_DAYS}日内有涨幅≥{SURGE_MIN}%的大阳线')
    out(f'  回测区间：{START_DATE} ~ {END_DATE}')
    out(f'  信号逻辑：前天在MA30上方 → 昨天跌破 → 今天站回（≤{ABOVE_MAX}%）')
    out(f'            + 近{SURGE_DAYS}交易日内至少1天涨幅≥{SURGE_MIN}% → 当天收盘买入')
    out(f'  扫描标的：{total_stocks} 只股票')
    out(f'  触发信号：{len(all_signals)} 次')
    out('=' * 80)

    # 汇总统计
    out()
    out('  【持有收益汇总】')
    out(f'  {"持有天数":>6}  {"信号次数":>8}  {"平均收益%":>10}  {"胜率%":>8}  {"平均盈利%":>10}  {"平均亏损%":>10}')
    out('  ' + '─' * 62)
    for d in range(1, HOLD_DAYS + 1):
        rets  = stats[d]['returns']
        total = stats[d]['total']
        if total == 0:
            out(f'  {d}天后         0        N/A        N/A')
            continue
        avg   = sum(rets) / total
        wins  = stats[d]['wins']
        win_r = wins / total * 100
        gains = [r for r in rets if r > 0]
        loses = [r for r in rets if r <= 0]
        avg_gain = sum(gains)/len(gains) if gains else 0
        avg_loss = sum(loses)/len(loses) if loses else 0
        out(f'  {d}天后    {total:>8}   {avg:>+9.2f}%  {win_r:>7.1f}%  {avg_gain:>+9.2f}%  {avg_loss:>+9.2f}%')

    # 按日期分组展示明细
    out()
    out('  【逐笔明细】')
    out(f'  {"日期":<10} {"代码":<12} {"买入价":>7} {"MA30":>7} {"离MA30":>6}  {"1天%":>7}  {"2天%":>7}  {"3天%":>7}')
    out('  ' + '─' * 72)

    cur_date = None
    date_rets = {d: [] for d in range(1, HOLD_DAYS+1)}
    date_count = 0

    def flush_date_summary(date):
        if date_count == 0: return
        out(f'  ── {date} 共{date_count}只  '
            + '  '.join(
                f'{d}天均{sum(date_rets[d])/len(date_rets[d]):+.2f}%'
                for d in range(1, HOLD_DAYS+1) if date_rets[d]
            ))

    for sig in all_signals:
        if sig['date'] != cur_date:
            if cur_date is not None:
                flush_date_summary(cur_date)
                out()
            cur_date = sig['date']
            date_rets  = {d: [] for d in range(1, HOLD_DAYS+1)}
            date_count = 0
            out(f'  ──────────── {cur_date} ────────────')

        r1, r2, r3 = sig['ret1'], sig['ret2'], sig['ret3']
        flag1 = '▲' if r1 > 0 else '▼'
        flag2 = '▲' if r2 > 0 else '▼'
        flag3 = '▲' if r3 > 0 else '▼'
        out(f'  {sig["date"]}  {sig["code"]:<12} {sig["buy"]:>7.2f} {sig["ma30"]:>7.2f} '
            f'+{sig["above_pct"]:>4.2f}%  '
            f'{flag1}{r1:>+5.2f}%  {flag2}{r2:>+5.2f}%  {flag3}{r3:>+5.2f}%')

        date_count += 1
        for d, r in [(1,r1),(2,r2),(3,r3)]:
            date_rets[d].append(r)

    if cur_date is not None:
        flush_date_summary(cur_date)

    out()
    out(f'  结果已保存：{OUT_PATH}')

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    run()

"""
回测策略：站回MA30（大涨过滤版）
  信号条件：
    - 前天收盘在MA30上方
    - 昨天收盘跌破MA30
    - 今天收盘站回MA30上方，且离MA30不超过 ABOVE_MAX%
    - 近两个月（约44交易日）内至少有一天单日涨幅 >= SURGE_MIN%
  买入：信号日收盘价
  持有：1/2/3天，分别计算收益率和胜率

用法：
  python 回测-站回MA30_大涨过滤版.py                     # 默认回测2026年1月
  python 回测-站回MA30_大涨过滤版.py 20260101 20260131   # 指定起止日期
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
INDEX_FILE = r'D:\soft\new_tdx\vipdoc\sh\lday\sh000001.day'
MIN_PRICE  = 3.0
ABOVE_MAX  = 3.0   # 站回MA30后距MA30不超过3%
HOLD_DAYS  = 3     # 最长持有天数
SURGE_DAYS = 22    # 近一个月约22交易日
SURGE_MIN  = 6.0   # 近两个月内至少有一天涨幅>=该值(%)

START_DATE = int(sys.argv[1]) if len(sys.argv) > 2 else 20260101
END_DATE   = int(sys.argv[2]) if len(sys.argv) > 2 else 20260131

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(OUT_DIR, exist_ok=True)
MONTH_TAG = str(START_DATE)[:6]
OUT_PATH = os.path.join(OUT_DIR, f'回测-站回MA30_大涨过滤版_{MONTH_TAG}.txt')


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


def load_index():
    recs = read_day_file(INDEX_FILE)
    result = {}
    for i in range(1, len(recs)):
        pct = (recs[i]['close'] - recs[i-1]['close']) / recs[i-1]['close'] * 100
        result[recs[i]['date']] = round(pct, 2)
    return result

def dlen(s):
    w = 0
    for c in str(s):
        w += 2 if '\u4e00' <= c <= '\u9fff' or '\uff00' <= c <= '\uffef' or '\u3000' <= c <= '\u303f' else 1
    return w

def ljust_d(s, width):
    return str(s) + ' ' * max(0, width - dlen(s))

def rjust_d(s, width):
    return ' ' * max(0, width - dlen(s)) + str(s)

def is_valid_stock(code):
    c = code.lower()
    if c.startswith('bj'): return False
    num = c[2:]
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


def run():
    st_codes = load_st_codes()
    all_signals = []
    stats = {d: {'returns': [], 'wins': 0, 'total': 0} for d in range(1, HOLD_DAYS+1)}
    total_stocks = 0
    filtered_surge = 0

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

            for i in range(2, len(records) - HOLD_DAYS):
                today = records[i]
                if today['date'] > END_DATE: break      # 已过区间，提前退出
                if today['date'] < START_DATE: continue
                if today['close'] < MIN_PRICE: continue
                if ma30[i] is None or ma30[i-1] is None or ma30[i-2] is None: continue

                yest    = records[i-1]
                day2ago = records[i-2]

                today_above = today['close']   >= ma30[i]
                yest_above  = yest['close']    >= ma30[i-1]
                day2_above  = day2ago['close'] >= ma30[i-2]

                if not (day2_above and not yest_above and today_above): continue
                above_pct = (today['close'] - ma30[i]) / ma30[i] * 100
                if above_pct > ABOVE_MAX: continue

                # 近两个月内至少有一天涨幅超过SURGE_MIN%
                start_j = max(1, i - SURGE_DAYS)
                has_surge = any(
                    (records[j]['close'] - records[j-1]['close']) / records[j-1]['close'] * 100 >= SURGE_MIN
                    for j in range(start_j, i + 1)
                )
                if not has_surge:
                    filtered_surge += 1
                    continue

                buy_price = today['close']
                rets = {d: (records[i+d]['close'] - buy_price) / buy_price * 100
                        for d in range(1, HOLD_DAYS+1)}

                all_signals.append({
                    'date': today['date'], 'code': code,
                    'buy': round(buy_price, 2), 'ma30': round(ma30[i], 2),
                    'above_pct': round(above_pct, 2),
                    'ret1': round(rets[1], 2), 'ret2': round(rets[2], 2), 'ret3': round(rets[3], 2),
                })
                for d in range(1, HOLD_DAYS+1):
                    stats[d]['returns'].append(rets[d])
                    stats[d]['total'] += 1
                    if rets[d] > 0: stats[d]['wins'] += 1

    all_signals.sort(key=lambda x: (x['date'], x['code']))
    index_pct = load_index()

    # 按信号日聚合
    day_data = defaultdict(lambda: {1:[], 2:[], 3:[]})
    for sig in all_signals:
        for d in range(1, HOLD_DAYS+1):
            day_data[sig['date']][d].append(sig[f'ret{d}'])

    lines = []
    def out(s=''):
        lines.append(s); print(s)

    def winr(rets):
        if not rets: return '   N/A'
        return f'{sum(1 for r in rets if r > 0)/len(rets)*100:>6.1f}%'

    out('=' * 84)
    out(f'  回测策略：站回MA30 大涨过滤版')
    out(f'  回测区间：{START_DATE} ~ {END_DATE}')
    out(f'  信号逻辑：前天上方->昨天跌破->今天站回(<={ABOVE_MAX}%)')
    out(f'            + 近{SURGE_DAYS}交易日内至少1天涨幅>={SURGE_MIN}% -> 当天收盘买入')
    out(f'  扫描标的：{total_stocks} 只股票    触发信号：{len(all_signals)} 次（因大涨条件剔除 {filtered_surge} 次）')
    out('=' * 84)
    out()

    # ── 整体汇总 ─────────────────────────────────────────────────
    out('  【持有收益汇总】')
    out(f'  {"持有天数":>6}  {"信号次数":>8}  {"平均收益%":>10}  {"胜率%":>8}  {"平均盈利%":>10}  {"平均亏损%":>10}')
    out('  ' + '-' * 64)
    for d in range(1, HOLD_DAYS+1):
        rets  = stats[d]['returns']
        total = stats[d]['total']
        if total == 0: continue
        avg      = sum(rets) / total
        win_r    = stats[d]['wins'] / total * 100
        gains    = [r for r in rets if r > 0]
        loses    = [r for r in rets if r <= 0]
        avg_gain = sum(gains)/len(gains) if gains else 0
        avg_loss = sum(loses)/len(loses) if loses else 0
        out(f'  {d}天后    {total:>8}   {avg:>+9.2f}%  {win_r:>7.1f}%  {avg_gain:>+9.2f}%  {avg_loss:>+9.2f}%')

    # ── 按信号日汇总 ─────────────────────────────────────────────
    out()
    out('  【按信号日汇总（含大盘涨跌）】')
    out()
    W = 72
    out('  ' + '=' * W)
    hdr = ('  ' + ljust_d('信号日', 12) + ljust_d('大盘', 12)
           + rjust_d('数', 4)
           + rjust_d('1天胜率', 9) + rjust_d('2天胜率', 9) + rjust_d('3天胜率', 9))
    out(hdr)
    out('  ' + '-' * W)

    up_days   = {d: [] for d in range(1, HOLD_DAYS+1)}
    down_days = {d: [] for d in range(1, HOLD_DAYS+1)}

    for date in sorted(day_data.keys()):
        data    = day_data[date]
        mkt_pct = index_pct.get(date, 0)
        mkt_str = f'{"涨" if mkt_pct>=0 else "跌"}{mkt_pct:+.2f}%'
        cnt     = len(data[1])
        row = ('  ' + ljust_d(date, 12) + ljust_d(mkt_str, 12)
               + rjust_d(cnt, 4)
               + rjust_d(winr(data[1]), 9) + rjust_d(winr(data[2]), 9) + rjust_d(winr(data[3]), 9))
        out(row)
        for d in range(1, HOLD_DAYS+1):
            (up_days if mkt_pct >= 0 else down_days)[d].extend(data[d])

    out()
    out('  ' + '=' * W)

    def stat_row(label, rd):
        n = len(rd[1])
        if n == 0: return
        wrs = [winr(rd[d]) for d in range(1, HOLD_DAYS+1)]
        row = ('  ' + ljust_d(label, 12) + ljust_d('', 12)
               + rjust_d(n, 4)
               + rjust_d(wrs[0], 9) + rjust_d(wrs[1], 9) + rjust_d(wrs[2], 9))
        out(row)

    stat_row('【全部合计】',  {d: stats[d]['returns'] for d in range(1,4)})
    stat_row('  大盘涨日', up_days)
    stat_row('  大盘跌日', down_days)

    # ── 逐笔明细 ────────────────────────────────────────────────
    out()
    out('  【逐笔明细】')
    out(f'  {"日期":<10} {"代码":<12} {"买入价":>7} {"MA30":>7} {"离MA30":>6}  {"1天%":>7}  {"2天%":>7}  {"3天%":>7}')
    out('  ' + '-' * 72)

    cur_date = None
    date_rets = {d: [] for d in range(1, HOLD_DAYS+1)}
    date_count = 0

    def flush_date():
        if date_count == 0: return
        mkt = index_pct.get(cur_date, 0)
        mkt_str = f'大盘{"涨" if mkt>=0 else "跌"}{mkt:+.2f}%'
        out('  ' + mkt_str + '  ' + ' | '.join(
            f'{d}天胜率{winr(date_rets[d])}'
            for d in range(1, HOLD_DAYS+1) if date_rets[d]
        ) + f'  共{date_count}只')

    for sig in all_signals:
        if sig['date'] != cur_date:
            if cur_date is not None:
                flush_date()
                out()
            cur_date = sig['date']
            date_rets  = {d: [] for d in range(1, HOLD_DAYS+1)}
            date_count = 0
            out(f'  ---- {cur_date} ----')
        r1, r2, r3 = sig['ret1'], sig['ret2'], sig['ret3']
        out(f'  {sig["date"]}  {sig["code"]:<12} {sig["buy"]:>7.2f} {sig["ma30"]:>7.2f} '
            f'+{sig["above_pct"]:>4.2f}%  '
            f'{"+" if r1>0 else ""}{r1:>5.2f}%  {"+" if r2>0 else ""}{r2:>5.2f}%  {"+" if r3>0 else ""}{r3:>5.2f}%')
        date_count += 1
        for d, r in [(1,r1),(2,r2),(3,r3)]:
            date_rets[d].append(r)

    if cur_date: flush_date()
    out()
    out(f'  结果已保存：{OUT_PATH}')

    with open(OUT_PATH, 'w', encoding='utf-8-sig') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    run()

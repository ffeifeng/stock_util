"""
回测策略：站回MA30 + 大盘自适应确认版
  信号条件：
    - 前天收盘在MA30上方
    - 昨天收盘跌破MA30
    - 今天收盘站回MA30上方，且离MA30不超过 ABOVE_MAX%
  买入规则（根据信号日大盘方向）：
    - 大盘上涨日：当天收盘直接买入（无需等待）
    - 大盘下跌日：次日仍在MA30上方才买入（次日收盘买入）
  持有：买入后 1/2/3天，分别计算收益率和胜率
  额外剔除：688开头科创板

用法：
  python 回测-站回MA30_次日确认版.py                     # 默认回测2026年1月
  python 回测-站回MA30_次日确认版.py 20260101 20260131   # 指定起止日期
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
ABOVE_MAX  = 3.0
HOLD_DAYS  = 3

START_DATE = int(sys.argv[1]) if len(sys.argv) > 2 else 20260101
END_DATE   = int(sys.argv[2]) if len(sys.argv) > 2 else 20260131

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, f'回测-站回MA30_自适应确认版_{START_DATE}_{END_DATE}.txt')


def read_day_file(path):
    records = []
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32: break
                date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
                records.append({'date': date, 'open': o/100, 'close': c/100})
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


def run():
    st_codes  = load_st_codes()
    index_pct = load_index()

    all_signals      = []
    stats            = {d: {'returns': [], 'wins': 0, 'total': 0} for d in range(1, HOLD_DAYS+1)}
    day_data         = defaultdict(lambda: {1:[], 2:[], 3:[]})
    total_stocks     = 0
    rejected_confirm = 0
    direct_buy_cnt   = 0
    confirm_buy_cnt  = 0

    for market, data_dir in DATA_DIRS.items():
        if not os.path.exists(data_dir): continue
        for fname in os.listdir(data_dir):
            if not fname.endswith('.day'): continue
            code = fname[:-4]
            if not is_valid_stock(code): continue
            if code[2:] in st_codes: continue

            records = read_day_file(os.path.join(data_dir, fname))
            if len(records) < 35 + 1 + HOLD_DAYS: continue

            closes = [r['close'] for r in records]
            ma30 = calc_ma(closes, 30)
            total_stocks += 1

            for i in range(2, len(records) - 1 - HOLD_DAYS):
                today = records[i]
                if today['date'] > END_DATE: break
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

                mkt_pct = index_pct.get(today['date'], 0)

                if mkt_pct >= 0:
                    # 大盘涨：当天直接买入
                    buy_price       = today['close']
                    buy_date        = today['date']
                    buy_offset      = 0
                    buy_type        = '直接'
                    direct_buy_cnt += 1
                else:
                    # 大盘跌：等次日确认
                    confirm   = records[i+1]
                    ma30_conf = ma30[i+1]
                    if ma30_conf is None: continue
                    if confirm['close'] < ma30_conf:
                        rejected_confirm += 1
                        continue
                    buy_price       = confirm['close']
                    buy_date        = confirm['date']
                    buy_offset      = 1
                    buy_type        = '确认'
                    confirm_buy_cnt += 1

                rets = {d: (records[i + buy_offset + d]['close'] - buy_price) / buy_price * 100
                        for d in range(1, HOLD_DAYS+1)}

                all_signals.append({
                    'signal_date':  today['date'],
                    'buy_date':     buy_date,
                    'buy_type':     buy_type,
                    'code':         code,
                    'signal_close': round(today['close'], 2),
                    'buy':          round(buy_price, 2),
                    'ma30':         round(ma30[i + buy_offset], 2),
                    'ret1': round(rets[1], 2),
                    'ret2': round(rets[2], 2),
                    'ret3': round(rets[3], 2),
                })
                for d in range(1, HOLD_DAYS+1):
                    stats[d]['returns'].append(rets[d])
                    stats[d]['total'] += 1
                    if rets[d] > 0: stats[d]['wins'] += 1
                    day_data[buy_date][d].append(rets[d])

    all_signals.sort(key=lambda x: (x['buy_date'], x['code']))

    lines = []
    def out(s=''):
        lines.append(s); print(s)

    out('=' * 88)
    out(f'  回测策略：站回MA30 自适应确认版（离MA30<={ABOVE_MAX}%，去掉688）')
    out(f'  回测区间：{START_DATE} ~ {END_DATE}')
    out(f'  买入规则：大盘涨 → 当天直接买入  |  大盘跌 → 次日仍在MA30上方才买入')
    out(f'  扫描标的：{total_stocks} 只')
    out(f'  触发信号：{len(all_signals)} 次（直接买入 {direct_buy_cnt} 次，次日确认买入 {confirm_buy_cnt} 次，确认被过滤 {rejected_confirm} 次）')
    out('=' * 88)
    out()

    # ── 汇总统计 ────────────────────────────────────────────────────
    out('  【持有收益汇总（买入日起算）】')
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

    # ── 按买入日汇总 ─────────────────────────────────────────────────
    buy_to_signal = defaultdict(set)
    buy_to_type   = {}
    for sig in all_signals:
        buy_to_signal[sig['buy_date']].add(sig['signal_date'])
        buy_to_type[sig['buy_date']] = sig['buy_type']

    out()
    out('  【按买入日汇总（含大盘涨跌）】')
    out(f'  说明：买入日大盘涨→信号日当天买；大盘跌→次日确认后买')
    out()
    W = 76
    out('  ' + '=' * W)
    hdr = ('  ' + ljust_d('买入日', 12) + ljust_d('信号日', 10) + ljust_d('方式', 6)
           + rjust_d('大盘', 10) + rjust_d('数', 5)
           + rjust_d('1天胜率', 9) + rjust_d('2天胜率', 9) + rjust_d('3天胜率', 9))
    out(hdr)
    out('  ' + '-' * W)

    up_days   = {1:[], 2:[], 3:[]}
    down_days = {1:[], 2:[], 3:[]}

    for date in sorted(day_data.keys()):
        data     = day_data[date]
        idx_pct  = index_pct.get(date, 0)
        mkt_str  = f'{"涨" if idx_pct>=0 else "跌"}{idx_pct:+.2f}%'
        sig_short = ','.join(f'{str(d)[4:6]}-{str(d)[6:8]}' for d in sorted(buy_to_signal[date]))
        btype    = buy_to_type.get(date, '')

        def winr(rets):
            if not rets: return '   N/A'
            return f'{sum(1 for r in rets if r > 0)/len(rets)*100:>6.1f}%'

        cnt = len(data[1])
        row = ('  ' + ljust_d(date, 12) + ljust_d(sig_short, 10) + ljust_d(btype, 6)
               + rjust_d(mkt_str, 10) + rjust_d(cnt, 5)
               + rjust_d(winr(data[1]), 9) + rjust_d(winr(data[2]), 9) + rjust_d(winr(data[3]), 9))
        out(row)

        for d in range(1, HOLD_DAYS+1):
            (up_days if idx_pct >= 0 else down_days)[d].extend(data[d])

    out()
    out('  ' + '=' * W)

    def stat_row(label, rd):
        n = len(rd[1])
        if n == 0: return
        wrs = [f'{sum(1 for r in rd[d] if r>0)/len(rd[d])*100:>6.1f}%' if rd[d] else '   N/A'
               for d in range(1, HOLD_DAYS+1)]
        row = ('  ' + ljust_d(label, 12) + ljust_d('', 10) + ljust_d('', 6)
               + rjust_d('', 10) + rjust_d(n, 5)
               + rjust_d(wrs[0], 9) + rjust_d(wrs[1], 9) + rjust_d(wrs[2], 9))
        out(row)

    stat_row('【全部合计】',    {d: stats[d]['returns'] for d in range(1,4)})
    stat_row('  大盘涨直接买', up_days)
    stat_row('  大盘跌确认买', down_days)

    # ── 逐笔明细 ────────────────────────────────────────────────────
    out()
    out('  【逐笔明细（按买入日排列）】')
    out(f'  {"信号日":<10} {"买入日":<10} {"方式":<4} {"代码":<12} {"信号收":>7} {"买入价":>7} {"MA30":>7}'
        f'  {"1天%":>7}  {"2天%":>7}  {"3天%":>7}')
    out('  ' + '-' * 86)
    cur = None
    for sig in all_signals:
        if sig['buy_date'] != cur:
            cur = sig['buy_date']
            out(f'  ---- 买入日 {cur} ({sig["buy_type"]}) ----')
        r1, r2, r3 = sig['ret1'], sig['ret2'], sig['ret3']
        out(f'  {sig["signal_date"]}  {sig["buy_date"]}  {sig["buy_type"]:4}  {sig["code"]:<12}'
            f' {sig["signal_close"]:>7.2f} {sig["buy"]:>7.2f} {sig["ma30"]:>7.2f}'
            f'  {"+" if r1>0 else ""}{r1:>5.2f}%'
            f'  {"+" if r2>0 else ""}{r2:>5.2f}%'
            f'  {"+" if r3>0 else ""}{r3:>5.2f}%')

    out()
    out(f'  结果已保存：{OUT_PATH}')

    with open(OUT_PATH, 'w', encoding='utf-8-sig') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    run()

"""
回测策略：站回MA30 + 跌日确认版（纯跌日确认逻辑）
  信号条件：
    - 前天收盘在MA30上方
    - 昨天收盘跌破MA30
    - 今天收盘站回MA30上方，且离MA30不超过 ABOVE_MAX%
    - 信号日大盘下跌（只取跌日信号）
  确认条件：
    - 次日收盘仍在MA30上方（确认站稳）
  买入：次日（确认日）收盘价
  持有：确认日后 1/2/3天，分别计算收益率和胜率
  额外剔除：688开头科创板

用法：
  python 回测-站回MA30_跌日确认版.py 20260201 20260228
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

START_DATE = int(sys.argv[1]) if len(sys.argv) > 2 else 20260201
END_DATE   = int(sys.argv[2]) if len(sys.argv) > 2 else 20260228

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(OUT_DIR, exist_ok=True)
MONTH_TAG = str(START_DATE)[:6]
OUT_PATH = os.path.join(OUT_DIR, f'回测-站回MA30_跌日确认版_{MONTH_TAG}.txt')


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
    skipped_up       = 0   # 大盘涨日跳过的信号数
    rejected_confirm = 0   # 大盘跌但次日跌破MA30被过滤的数量

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

                # 只处理大盘下跌日
                if mkt_pct >= 0:
                    skipped_up += 1
                    continue

                # 次日确认
                confirm   = records[i+1]
                ma30_conf = ma30[i+1]
                if ma30_conf is None: continue
                if confirm['close'] < ma30_conf:
                    rejected_confirm += 1
                    continue

                buy_price = confirm['close']
                buy_date  = confirm['date']

                rets = {d: (records[i + 1 + d]['close'] - buy_price) / buy_price * 100
                        for d in range(1, HOLD_DAYS+1)}

                all_signals.append({
                    'signal_date':  today['date'],
                    'buy_date':     buy_date,
                    'code':         code,
                    'mkt_pct':      mkt_pct,
                    'signal_close': round(today['close'], 2),
                    'buy':          round(buy_price, 2),
                    'ma30':         round(ma30_conf, 2),
                    'ret1': round(rets[1], 2),
                    'ret2': round(rets[2], 2),
                    'ret3': round(rets[3], 2),
                })
                for d in range(1, HOLD_DAYS+1):
                    stats[d]['returns'].append(rets[d])
                    stats[d]['total'] += 1
                    if rets[d] > 0: stats[d]['wins'] += 1
                    day_data[buy_date][d].append(rets[d])

    all_signals.sort(key=lambda x: (x['buy_date'], x['signal_date'], x['code']))

    lines = []
    def out(s=''):
        lines.append(s); print(s)

    out('=' * 88)
    out(f'  回测策略：站回MA30 跌日确认版（离MA30<={ABOVE_MAX}%，去掉688）')
    out(f'  回测区间：{START_DATE} ~ {END_DATE}（信号日范围）')
    out(f'  筛选逻辑：仅保留信号日大盘下跌的信号，且次日仍在MA30上方才买入')
    out(f'  买入价格：确认日（信号日+1）收盘价，持有1/2/3天')
    out(f'  扫描标的：{total_stocks} 只')
    out(f'  触发信号：{len(all_signals)} 次   大盘涨日跳过：{skipped_up} 次   确认被过滤：{rejected_confirm} 次')
    out('=' * 88)
    out()

    # ── 汇总统计 ─────────────────────────────────────────────────────
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
    # 构建 buy_date -> [(signal_date, mkt_pct, [rets1], [rets2], [rets3])]
    from collections import OrderedDict
    sig_detail = defaultdict(lambda: defaultdict(lambda: {1:[], 2:[], 3:[]}))
    mkt_by_signal = {}
    for sig in all_signals:
        mkt_by_signal[sig['signal_date']] = sig['mkt_pct']
        for d in range(1, HOLD_DAYS+1):
            sig_detail[sig['buy_date']][sig['signal_date']][d].append(
                getattr(sig, 'ret'+str(d), None) or sig[f'ret{d}'])

    def winr(rets):
        if not rets: return '   N/A'
        return f'{sum(1 for r in rets if r > 0)/len(rets)*100:>6.1f}%'

    out()
    out('  【按买入日汇总（含大盘涨跌）】')
    out(f'  说明：信号日大盘下跌，次日仍在MA30上方 → 次日收盘买入')
    out()
    W = 76
    out('  ' + '=' * W)
    hdr = ('  ' + ljust_d('买入日', 12) + ljust_d('信号日', 10) + ljust_d('信号日大盘', 12)
           + rjust_d('数', 4)
           + rjust_d('1天胜率', 9) + rjust_d('2天胜率', 9) + rjust_d('3天胜率', 9))
    out(hdr)
    out('  ' + '-' * W)

    for buy_date in sorted(sig_detail.keys()):
        total_data  = day_data[buy_date]
        sig_dates   = sorted(sig_detail[buy_date].keys())
        buy_cnt     = len(total_data[1])

        for idx, sdate in enumerate(sig_dates):
            sd       = sig_detail[buy_date][sdate]
            mkt_pct  = mkt_by_signal.get(sdate, 0)
            mkt_str  = f'跌{mkt_pct:+.2f}%'
            sig_str  = f'{str(sdate)[4:6]}-{str(sdate)[6:8]}'
            cnt      = len(sd[1])

            if idx == 0:
                # 第一个信号日：显示买入日 + 本买入日合计胜率
                buy_str = str(buy_date)
                row = ('  ' + ljust_d(buy_str, 12) + ljust_d(sig_str, 10) + ljust_d(mkt_str, 12)
                       + rjust_d(cnt, 4)
                       + rjust_d(winr(sd[1]), 9) + rjust_d(winr(sd[2]), 9) + rjust_d(winr(sd[3]), 9))
                # 如果有多个信号日，末尾追加合计
                if len(sig_dates) > 1:
                    row += f'   (合计{buy_cnt}笔: {winr(total_data[1])}/{winr(total_data[2])}/{winr(total_data[3])})'
            else:
                # 后续信号日：买入日留空，缩进显示
                row = ('  ' + ljust_d('', 12) + ljust_d(sig_str, 10) + ljust_d(mkt_str, 12)
                       + rjust_d(cnt, 4)
                       + rjust_d(winr(sd[1]), 9) + rjust_d(winr(sd[2]), 9) + rjust_d(winr(sd[3]), 9))
            out(row)

    out()
    out('  ' + '=' * W)
    # 总计行
    tot = len(all_signals)
    if tot:
        wrs = [f'{stats[d]["wins"]/stats[d]["total"]*100:>6.1f}%' if stats[d]['total'] else '   N/A'
               for d in range(1, HOLD_DAYS+1)]
        row = ('  ' + ljust_d('【合计】', 12) + ljust_d('', 10) + ljust_d('', 12)
               + rjust_d(tot, 4)
               + rjust_d(wrs[0], 9) + rjust_d(wrs[1], 9) + rjust_d(wrs[2], 9))
        out(row)

    # ── 逐笔明细 ────────────────────────────────────────────────────
    out()
    out('  【逐笔明细（按买入日排列）】')
    out(f'  {"信号日":<10} {"信号大盘":>8} {"买入日":<10} {"代码":<12} {"信号收":>7} {"买入价":>7} {"MA30":>7}'
        f'  {"1天%":>7}  {"2天%":>7}  {"3天%":>7}')
    out('  ' + '-' * 90)
    cur = None
    for sig in all_signals:
        if sig['buy_date'] != cur:
            cur = sig['buy_date']
            out(f'  ---- 买入日 {cur} ----')
        r1, r2, r3 = sig['ret1'], sig['ret2'], sig['ret3']
        out(f'  {sig["signal_date"]}  {sig["mkt_pct"]:>+7.2f}%  {sig["buy_date"]}  {sig["code"]:<12}'
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

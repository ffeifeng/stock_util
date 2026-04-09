"""
按信号日汇总回测结果：
  - 列出每个信号日的 1/2/3天 平均收益和胜率
  - 标注当天大盘（上证指数）涨跌方向
  - 对比大盘涨跌与策略胜率的关系

默认使用：基础版逻辑（无大涨过滤，去掉688）
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
INDEX_FILE  = r'D:\soft\new_tdx\vipdoc\sh\lday\sh000001.day'  # 上证指数
MIN_PRICE   = 3.0
ABOVE_MAX   = 3.0
HOLD_DAYS   = 3
START_DATE  = int(sys.argv[1]) if len(sys.argv) > 2 else 20260101
END_DATE    = int(sys.argv[2]) if len(sys.argv) > 2 else 20260131

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, f'分析-按日汇总_基础版_{START_DATE}_{END_DATE}.txt')


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
    """读取上证指数，返回 {date: pct_change}"""
    recs = read_day_file(INDEX_FILE)
    result = {}
    for i in range(1, len(recs)):
        prev = recs[i-1]['close']
        curr = recs[i]['close']
        pct  = (curr - prev) / prev * 100 if prev else 0
        result[recs[i]['date']] = round(pct, 2)
    return result


def run():
    st_codes  = load_st_codes()
    index_pct = load_index()

    # date -> {ret1:[], ret2:[], ret3:[]}
    day_data = defaultdict(lambda: {1:[], 2:[], 3:[]})

    total_stocks = 0
    for market, data_dir in DATA_DIRS.items():
        if not os.path.exists(data_dir): continue
        for fname in os.listdir(data_dir):
            if not fname.endswith('.day'): continue
            code = fname[:-4]
            if not is_valid_stock(code): continue
            if code[2:] in st_codes: continue

            with open(os.path.join(data_dir, fname), 'rb') as f:
                raw = f.read()
            n = len(raw) // 32
            if n < 35 + HOLD_DAYS: continue

            records = []
            for k in range(n):
                chunk = raw[k*32:(k+1)*32]
                date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
                records.append({'date': date, 'open': o/100, 'close': c/100})

            closes = [r['close'] for r in records]
            ma30 = calc_ma(closes, 30)
            total_stocks += 1

            for i in range(2, n - HOLD_DAYS):
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

                buy = today['close']
                for d in range(1, HOLD_DAYS+1):
                    ret = (records[i+d]['close'] - buy) / buy * 100
                    day_data[today['date']][d].append(ret)

    # ── 输出 ────────────────────────────────────────────────────────
    sorted_dates = sorted(day_data.keys())

    lines = []
    def out(s=''):
        lines.append(s); print(s)

    out('=' * 100)
    out(f'  策略：站回MA30 基础版（离MA30<={ABOVE_MAX}%，去掉688）  区间：{START_DATE}~{END_DATE}')
    out(f'  扫描标的：{total_stocks} 只   信号日数：{len(sorted_dates)} 天')
    out('=' * 100)
    out()
    out(f'  {"信号日":>10}  {"大盘":>6}  {"信号数":>5}'
        f'  {"1天均收":>8}  {"1天胜率":>7}'
        f'  {"2天均收":>8}  {"2天胜率":>7}'
        f'  {"3天均收":>8}  {"3天胜率":>7}')
    out('  ' + '─' * 92)

    # 全局汇总
    all_rets = {1:[], 2:[], 3:[]}

    up_days   = {1:[], 2:[], 3:[]}   # 大盘上涨日的信号收益
    down_days = {1:[], 2:[], 3:[]}   # 大盘下跌日的信号收益

    for date in sorted_dates:
        data    = day_data[date]
        idx_pct = index_pct.get(date, 0)
        mkt_tag = f'▲{idx_pct:+.2f}%' if idx_pct >= 0 else f'▼{idx_pct:+.2f}%'

        def fmt(rets):
            if not rets: return '   N/A  ', '   N/A '
            avg  = sum(rets)/len(rets)
            winr = sum(1 for r in rets if r > 0) / len(rets) * 100
            return f'{avg:>+7.2f}%', f'{winr:>6.1f}%'

        r1, w1 = fmt(data[1])
        r2, w2 = fmt(data[2])
        r3, w3 = fmt(data[3])
        cnt = len(data[1])

        out(f'  {date}  {mkt_tag:>8}  {cnt:>5}'
            f'  {r1}  {w1}'
            f'  {r2}  {w2}'
            f'  {r3}  {w3}')

        for d in range(1, HOLD_DAYS+1):
            all_rets[d].extend(data[d])
            if idx_pct >= 0:
                up_days[d].extend(data[d])
            else:
                down_days[d].extend(data[d])

    # ── 汇总统计 ────────────────────────────────────────────────────
    out()
    out('  ' + '─' * 92)

    def stat_row(label, rets_dict):
        parts = []
        for d in range(1, HOLD_DAYS+1):
            rets = rets_dict[d]
            if not rets:
                parts.append('   N/A     N/A ')
                continue
            avg  = sum(rets)/len(rets)
            winr = sum(1 for r in rets if r > 0)/len(rets)*100
            parts.append(f'{avg:>+7.2f}%  {winr:>6.1f}%')
        total = len(rets_dict[1])
        out(f'  {label:<12}  {"":>6}  {total:>5}  ' + '  '.join(parts))

    stat_row('【全部合计】',  all_rets)
    stat_row('  大盘上涨日', up_days)
    stat_row('  大盘下跌日', down_days)

    out()
    out(f'  大盘上涨日信号数：{len(up_days[1])}   大盘下跌日信号数：{len(down_days[1])}')
    out(f'  结果已保存：{OUT_PATH}')

    with open(OUT_PATH, 'w', encoding='utf-8-sig') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    run()

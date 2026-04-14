"""
回测：涨停后连续3天小涨（含净特大资金过滤），第四天买入
条件：
  Day0 : 当日涨停
  Day1~3: 每天涨幅 0% < pct ≤ 5%，且当天 超大单净流入（净特大资金）> 0
  Day4 : 以当日开盘价买入
  退出 : 持有 3/5/7 个交易日后，以收盘价计算收益率

数据来源：
  - 行情（OHLCV）：本地 TDX .day 文件
  - 净特大资金：efinance（东方财富，与TDX ZJBY 方向一致，约120天历史）

用法：
  python 回测-涨停后小涨买入_净特大v2.py
"""
import struct, os, sys, time
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# 清除系统代理，避免代理拦截东方财富 API 请求
for _k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
           'ALL_PROXY', 'all_proxy']:
    os.environ.pop(_k, None)
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

# ── 参数 ──────────────────────────────────────────────────────────────────────
DATA_DIRS = {
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
}
MIN_PRICE       = 3.0
SMALL_GAIN_MIN  = 0.0
SMALL_GAIN_MAX  = 5.0
HOLD_DAYS       = [3, 5, 7]

# efinance 约提供最近 120 个交易日的资金流数据
# 从 2025-10-15 起扫（确保 efinance 数据能覆盖）
SCAN_START = 20251015
SCAN_END   = int(datetime.now().strftime('%Y%m%d'))

# efinance 资金流缓存目录
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', 'data', 'fund_flow_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', 'output', '回测结果')
os.makedirs(OUT_DIR, exist_ok=True)
OUT_FILE = os.path.join(OUT_DIR,
    f'回测-涨停后小涨买入_净特大v2_{SCAN_START}_{SCAN_END}.txt')


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def read_day_file(path):
    records = []
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32: break
                date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
                records.append({
                    'date':  date,
                    'open':  o / 100,
                    'high':  h / 100,
                    'low':   l / 100,
                    'close': c / 100,
                })
    except: pass
    return records


def is_valid_stock(code):
    c = code.lower()
    if c.startswith('bj'): return False
    num = c[2:]
    if c.startswith('sh'): return num[:3] in ['600','601','602','603','604','605','688']
    if c.startswith('sz'): return num[:3] in ['000','001','002','003','300','301']
    return False


def get_limit_pct(code):
    num = code[2:]
    if code.startswith('sh') and num[:3] == '688': return 20.0
    if code.startswith('sz') and num[:3] in ['300','301']: return 20.0
    return 10.0


def is_limit_up(code, close, prev_close):
    if prev_close <= 0: return False
    limit_price = round(prev_close * (1 + get_limit_pct(code) / 100), 2)
    return close >= limit_price * 0.998


def load_st_codes():
    st_set = set()
    p = r'D:\soft\st_codes.txt'
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                c = line.strip()
                if c: st_set.add(c)
    return st_set


def fmt_date(d):
    s = str(d)
    return f'{s[:4]}-{s[4:6]}-{s[6:8]}'


# ── efinance 资金流数据（带本地 CSV 缓存）────────────────────────────────────

_flow_cache = {}   # code -> {date_str: float}  单位：元

def _load_flow_for_code(code):
    """
    用 efinance 获取 code（如 '600036'）的超大单净流入历史。
    优先读本地缓存 CSV；若无则联网拉取（带重试）后保存。
    返回 {date_str: float}，单位：元。
    """
    csv_path = os.path.join(CACHE_DIR, f'{code}.csv')
    data = {}

    # 尝试读本地缓存（文件存在且非空才使用）
    if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
        try:
            with open(csv_path, encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        data[parts[0]] = float(parts[1])
            return data
        except:
            pass

    # 联网拉取（最多重试 3 次，指数退避）
    import efinance as ef
    for attempt in range(3):
        try:
            df = ef.stock.get_history_bill(code)
            if df is None or len(df) == 0:
                time.sleep(1.0)
                continue
            df = df.sort_values('日期')
            for _, row in df.iterrows():
                d = str(row['日期'])
                v = row['超大单净流入']
                if v is not None and str(v) != 'nan':
                    data[d] = float(v)
            if data:
                # 写缓存
                with open(csv_path, 'w', encoding='utf-8') as f:
                    for d, v in sorted(data.items()):
                        f.write(f'{d},{v}\n')
                return data
            time.sleep(1.0 * (attempt + 1))
        except Exception as e:
            wait = 1.5 * (attempt + 1)
            if attempt < 2:
                time.sleep(wait)
            else:
                print(f'    [warn] {code} 资金流拉取失败: {e}')

    return data


def get_net_super(code, date_int):
    """
    查询 code（如 'sh600036'）在 date_int（如 20251014）的超大单净流入（元）。
    正值 = 净买入；无数据返回 None。
    """
    num_code = code[2:]   # 去掉 sh/sz 前缀
    if num_code not in _flow_cache:
        _flow_cache[num_code] = _load_flow_for_code(num_code)
    records = _flow_cache[num_code]
    date_str = fmt_date(date_int)   # '2025-10-14'
    return records.get(date_str)


def prefetch_flow(codes):
    """批量预拉取资金流，有进度提示"""
    unique = sorted(set(c[2:] for c in codes))
    total = len(unique)
    print(f'  预拉取资金流：{total} 只股票', flush=True)
    for i, num_code in enumerate(unique, 1):
        if num_code not in _flow_cache:
            _flow_cache[num_code] = _load_flow_for_code(num_code)
        if i % 20 == 0:
            print(f'    {i}/{total}', flush=True)
        time.sleep(0.8)   # 避免触发限流
    print(f'  预拉取完成', flush=True)


# ── 第一步：从本地数据找初步信号 ──────────────────────────────────────────────

def find_raw_signals(st_codes):
    raw = []
    for market, data_dir in DATA_DIRS.items():
        if not os.path.exists(data_dir): continue
        files = [f for f in os.listdir(data_dir) if f.endswith('.day')]
        valid = [f for f in files if is_valid_stock(f[:-4]) and f[2:-4] not in st_codes]
        total = len(valid)
        print(f'  扫描 {market.upper()} {total} 只...', flush=True)
        for vi, fname in enumerate(valid):
            if (vi + 1) % 500 == 0:
                print(f'    进度 {vi+1}/{total}', flush=True)
            code    = fname[:-4]
            records = read_day_file(os.path.join(data_dir, fname))
            n = len(records)
            start_i = max(1, n - 300)
            for i in range(start_i, n):
                if records[i]['date'] < SCAN_START: continue
                if records[i]['date'] > SCAN_END:   break
                prev_c = records[i-1]['close']
                if not is_limit_up(code, records[i]['close'], prev_c): continue
                if records[i]['close'] < MIN_PRICE: continue

                ok = True
                day_pcts = []
                day_dates = []
                for offset in range(1, 4):
                    j = i + offset
                    if j >= n: ok = False; break
                    prev_close = records[j-1]['close']
                    if prev_close <= 0: ok = False; break
                    pct = (records[j]['close'] - prev_close) / prev_close * 100
                    if not (SMALL_GAIN_MIN < pct <= SMALL_GAIN_MAX): ok = False; break
                    day_pcts.append(round(pct, 2))
                    day_dates.append(fmt_date(records[j]['date']))
                if not ok: continue

                entry_idx = i + 4
                if entry_idx >= n: continue
                entry_price = records[entry_idx]['open']
                if entry_price <= 0: continue

                forward = {}
                for hold in HOLD_DAYS:
                    exit_idx = entry_idx + hold
                    if exit_idx < n:
                        forward[hold] = round(
                            (records[exit_idx]['close'] - entry_price) / entry_price * 100, 2)
                    else:
                        forward[hold] = None

                raw.append({
                    'code':        code,
                    'lim_date':    records[i]['date'],
                    'day_dates':   day_dates,
                    'day1_pct':    day_pcts[0],
                    'day2_pct':    day_pcts[1],
                    'day3_pct':    day_pcts[2],
                    'entry_date':  records[entry_idx]['date'],
                    'entry_price': round(entry_price, 2),
                    **{f'fwd_{h}d': forward[h] for h in HOLD_DAYS},
                })
        cnt = len([r for r in raw if r['code'][:2] == market])
        print(f'  {market.upper()} 扫描完成，命中 {cnt} 笔', flush=True)
    return raw


# ── 第二步：用 efinance 过滤净特大 ────────────────────────────────────────────

def apply_fund_flow_filter(raw_signals):
    """
    Day1~3 只要有 efinance 数据的日期，净流入必须 > 0。
    全部无数据 → 丢弃；部分有数据且均 > 0 → 保留。
    """
    all_codes = [s['code'] for s in raw_signals]
    prefetch_flow(all_codes)

    passed = []
    no_data_count = 0
    partial_count = 0
    full_count    = 0

    for sig in raw_signals:
        code      = sig['code']
        day_dates = sig['day_dates']

        has_data_days = 0
        ok = True
        flows = []

        for ds in day_dates:
            date_int = int(ds.replace('-', ''))
            net = get_net_super(code, date_int)
            flows.append(net)
            if net is not None:
                has_data_days += 1
                if net <= 0:
                    ok = False
                    break

        if has_data_days == 0:
            no_data_count += 1
            continue
        elif has_data_days < 3:
            partial_count += 1
        else:
            full_count += 1

        if ok:
            sig['flow1'] = round(flows[0] / 1e4, 0) if flows[0] is not None else None
            sig['flow2'] = round(flows[1] / 1e4, 0) if flows[1] is not None else None
            sig['flow3'] = round(flows[2] / 1e4, 0) if flows[2] is not None else None
            sig['data_days'] = has_data_days
            passed.append(sig)

    print(f'  完整3天数据: {full_count} 笔  部分数据: {partial_count} 笔  无数据: {no_data_count} 笔', flush=True)
    print(f'  过滤后保留: {len(passed)} 笔', flush=True)
    return passed


# ── 统计与输出 ─────────────────────────────────────────────────────────────────

def pct_bucket(pct):
    if pct <= -10: return '≤-10%'
    if pct <=  -5: return '-10%~-5%'
    if pct <=  -3: return '-5%~-3%'
    if pct <    0: return '-3%~0%'
    if pct <    3: return '0%~+3%'
    if pct <    5: return '+3%~+5%'
    if pct <   10: return '+5%~+10%'
    return '≥+10%'

BUCKETS = ['≤-10%', '-10%~-5%', '-5%~-3%', '-3%~0%',
           '0%~+3%', '+3%~+5%', '+5%~+10%', '≥+10%']


def report(all_hits, raw_count):
    lines = []
    def out(s=''):
        lines.append(s); print(s)

    out('=' * 80)
    out('【回测：涨停后连续3天小涨 + 净特大资金持续净流入，第四天买入】')
    out(f'扫描区间：{fmt_date(SCAN_START)} ~ {fmt_date(SCAN_END)}')
    out(f'条件：涨停 → Day1/2/3 每天 0%<涨幅≤5% 且超大单净流入>0 → Day4开盘买入')
    out(f'数据源：行情=本地TDX  资金流=efinance（东方财富）')
    out(f'初步信号（仅形态）：{raw_count} 笔   过滤后（含净特大）：{len(all_hits)} 笔')
    out('=' * 80)

    for hold in HOLD_DAYS:
        key   = f'fwd_{hold}d'
        valid = [h for h in all_hits if h[key] is not None]
        if not valid:
            out(f'\n持股 {hold} 天：数据不足'); continue

        wins   = [h for h in valid if h[key] > 0]
        losses = [h for h in valid if h[key] <= 0]
        avg_r  = sum(h[key] for h in valid)  / len(valid)
        avg_w  = sum(h[key] for h in wins)   / len(wins)   if wins   else 0
        avg_l  = sum(h[key] for h in losses) / len(losses) if losses else 0
        vals   = sorted(h[key] for h in valid)
        median = vals[len(vals) // 2]

        out()
        out(f'┌─ 持股 {hold} 天 ──────────────────────────────────────────────────')
        out(f'│  有效信号：{len(valid)} 笔  │  胜率：{len(wins)/len(valid)*100:.1f}%'
            f'  ({len(wins)}胜/{len(losses)}负)')
        out(f'│  平均收益：{avg_r:>+.2f}%  │  中位数：{median:>+.2f}%')
        out(f'│  平均盈利：{avg_w:>+.2f}%  │  平均亏损：{avg_l:>+.2f}%')
        dist = {b: 0 for b in BUCKETS}
        for h in valid:
            dist[pct_bucket(h[key])] += 1
        out('│  收益分布：')
        for b in BUCKETS:
            cnt = dist[b]
            bar = '█' * int(cnt / len(valid) * 100 / 2)
            out(f'│    {b:>12}  {cnt:>4}笔  {cnt/len(valid)*100:>5.1f}%  {bar}')
        out('└─────────────────────────────────────────────────────────────────')

    out()
    out('=' * 80)
    out(f'  信号明细（共 {len(all_hits)} 笔）')
    out('=' * 80)
    out(f'  {"排":>3}  {"代码":<10} {"涨停日":<12}'
        f' {"D1%":>5} {"净特大1":>9}'
        f' {"D2%":>5} {"净特大2":>9}'
        f' {"D3%":>5} {"净特大3":>9}'
        f' {"买入日":<12} {"买价":>7}'
        f' {"3日%":>6} {"5日%":>6} {"7日%":>6}')
    out('  ' + '─' * 110)

    def fmt(v): return f'{v:>+5.1f}%' if v is not None else '    --'
    def fmf(v): return f'{v:>+8.0f}万' if v is not None else '       --'

    for idx, h in enumerate(all_hits, 1):
        out(f'  {idx:>3}  {h["code"]:<10} {fmt_date(h["lim_date"]):<12}'
            f' {h["day1_pct"]:>+4.1f}% {fmf(h.get("flow1"))}'
            f' {h["day2_pct"]:>+4.1f}% {fmf(h.get("flow2"))}'
            f' {h["day3_pct"]:>+4.1f}% {fmf(h.get("flow3"))}'
            f' {fmt_date(h["entry_date"]):<12} {h["entry_price"]:>7.2f}'
            f' {fmt(h["fwd_3d"])} {fmt(h["fwd_5d"])} {fmt(h["fwd_7d"])}')

    out()
    out(f'  结果已保存：{OUT_FILE}')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


# ── 主入口 ────────────────────────────────────────────────────────────────────

def run():
    st_codes = load_st_codes()

    print('=' * 60)
    print(f'第一步：扫描本地K线，找形态信号（{fmt_date(SCAN_START)}~{fmt_date(SCAN_END)}）')
    print('=' * 60)
    raw = find_raw_signals(st_codes)
    raw.sort(key=lambda x: x['lim_date'])
    print(f'\n初步信号共 {len(raw)} 笔')

    print()
    print('=' * 60)
    print('第二步：拉取资金流数据（efinance），过滤净特大 > 0')
    print('=' * 60)
    hits = apply_fund_flow_filter(raw)
    hits.sort(key=lambda x: x['lim_date'])
    print(f'\n过滤后剩余 {len(hits)} 笔')

    print()
    print('=' * 60)
    print('第三步：统计结果')
    print('=' * 60)
    report(hits, len(raw))


if __name__ == '__main__':
    run()

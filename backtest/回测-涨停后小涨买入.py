"""
回测：涨停后连续3天小涨，第四天买入
条件：
  Day0 : 当日涨停（主板 ±10%，科创/创业板 ±20%）
  Day1~3: 每天涨幅均满足  0% < 涨幅 ≤ 5%（连续3天小涨，不跌也不超5%）
  Day4 : 以当日开盘价买入
  退出 : 分别在持有 3/5/7 个交易日后，以收盘价计算收益率

统计内容：
  - 总信号数
  - 各持有周期的胜率、平均收益、平均盈利、平均亏损
  - 盈亏分布（区间计数）

扫描区间：2025-01-01 至今
用法：
  python 回测-涨停后小涨买入.py
  python 回测-涨停后小涨买入.py 20250101 20260410
"""
import struct, os, sys
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# ── 参数 ──────────────────────────────────────────────────────────────────────
DATA_DIRS = {
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
}
MIN_PRICE        = 3.0
SMALL_GAIN_MIN   = 0.0    # Day1~3 涨幅下限（不含，必须 > 0）
SMALL_GAIN_MAX   = 5.0    # Day1~3 涨幅上限（含）
HOLD_DAYS        = [3, 5, 7]

if len(sys.argv) >= 3:
    SCAN_START = int(sys.argv[1])
    SCAN_END   = int(sys.argv[2])
else:
    SCAN_START = 20250101
    SCAN_END   = int(datetime.now().strftime('%Y%m%d'))

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', 'output', '回测结果')
os.makedirs(OUT_DIR, exist_ok=True)
OUT_FILE = os.path.join(OUT_DIR, f'回测-涨停后小涨买入_{SCAN_START}_{SCAN_END}.txt')


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


def pct_bucket(pct):
    """收益区间分组"""
    if pct <= -10: return '≤-10%'
    if pct <= -5:  return '-10%~-5%'
    if pct <= -3:  return '-5%~-3%'
    if pct <   0:  return '-3%~0%'
    if pct <   3:  return '0%~+3%'
    if pct <   5:  return '+3%~+5%'
    if pct <  10:  return '+5%~+10%'
    return '≥+10%'

BUCKETS = ['≤-10%', '-10%~-5%', '-5%~-3%', '-3%~0%',
           '0%~+3%', '+3%~+5%', '+5%~+10%', '≥+10%']


# ── 主回测逻辑 ────────────────────────────────────────────────────────────────

def backtest_stock(code, records):
    """对单只股票找出所有信号，返回命中记录列表"""
    hits = []
    n = len(records)

    for i in range(1, n):
        # Day0：当日涨停
        if records[i]['date'] < SCAN_START: continue
        if records[i]['date'] > SCAN_END:   break

        prev_close = records[i-1]['close']
        if not is_limit_up(code, records[i]['close'], prev_close): continue
        if records[i]['close'] < MIN_PRICE: continue

        # Day1~3：连续3天小涨
        ok = True
        for offset in range(1, 4):
            j = i + offset
            if j >= n:
                ok = False; break
            c_today = records[j]['close']
            c_prev  = records[j-1]['close']
            if c_prev <= 0:
                ok = False; break
            pct = (c_today - c_prev) / c_prev * 100
            if not (SMALL_GAIN_MIN < pct <= SMALL_GAIN_MAX):
                ok = False; break
        if not ok: continue

        # Day4：买入（以开盘价）
        entry_idx = i + 4
        if entry_idx >= n: continue
        entry_price = records[entry_idx]['open']
        if entry_price <= 0: continue

        # 计算各持有周期收益
        forward = {}
        for hold in HOLD_DAYS:
            exit_idx = entry_idx + hold
            if exit_idx < n:
                exit_price = records[exit_idx]['close']
                forward[hold] = round((exit_price - entry_price) / entry_price * 100, 2)
            else:
                forward[hold] = None

        # Day1~3 各日涨幅
        day_pcts = []
        for offset in range(1, 4):
            j = i + offset
            pct = (records[j]['close'] - records[j-1]['close']) / records[j-1]['close'] * 100
            day_pcts.append(round(pct, 2))

        hits.append({
            'code':        code,
            'lim_date':    records[i]['date'],
            'lim_close':   round(records[i]['close'], 2),
            'day1_pct':    day_pcts[0],
            'day2_pct':    day_pcts[1],
            'day3_pct':    day_pcts[2],
            'entry_date':  records[entry_idx]['date'],
            'entry_price': round(entry_price, 2),
            **{f'fwd_{h}d': forward[h] for h in HOLD_DAYS},
        })

    return hits


def run():
    st_codes = load_st_codes()
    all_hits = []

    total_files = 0
    for market, data_dir in DATA_DIRS.items():
        if not os.path.exists(data_dir): continue
        files = [f for f in os.listdir(data_dir) if f.endswith('.day')]
        valid = [f for f in files if is_valid_stock(f[:-4]) and f[2:-4] not in st_codes]
        total_files += len(valid)
        print(f'扫描 {market.upper()} {len(valid)} 只...', end=' ', flush=True)
        for fname in valid:
            code    = fname[:-4]
            records = read_day_file(os.path.join(data_dir, fname))
            if len(records) < 15: continue
            hits = backtest_stock(code, records)
            all_hits.extend(hits)
        print('完成')

    all_hits.sort(key=lambda x: x['lim_date'])
    print(f'\n共找到信号：{len(all_hits)} 笔\n')

    # ── 统计 ──────────────────────────────────────────────────────────────────
    lines = []
    def out(s=''):
        lines.append(s); print(s)

    out('=' * 72)
    out(f'【回测：涨停后连续3天小涨，第四天买入】')
    out(f'扫描区间：{fmt_date(SCAN_START)} ~ {fmt_date(SCAN_END)}')
    out(f'条件：涨停后 Day1/2/3 每天涨幅 0% < pct ≤ {SMALL_GAIN_MAX}%，Day4开盘买入')
    out(f'共找到信号：{len(all_hits)} 笔')
    out('=' * 72)

    for hold in HOLD_DAYS:
        key    = f'fwd_{hold}d'
        valid  = [h for h in all_hits if h[key] is not None]
        if not valid:
            out(f'\n持股 {hold} 天：无有效数据'); continue

        wins   = [h for h in valid if h[key] > 0]
        losses = [h for h in valid if h[key] <= 0]
        avg_r  = sum(h[key] for h in valid)  / len(valid)
        avg_w  = sum(h[key] for h in wins)   / len(wins)  if wins   else 0
        avg_l  = sum(h[key] for h in losses) / len(losses) if losses else 0
        median = sorted(h[key] for h in valid)[len(valid)//2]

        out()
        out(f'┌─ 持股 {hold} 天 ─────────────────────────────────────────────')
        out(f'│  有效信号：{len(valid)} 笔  │  胜率：{len(wins)/len(valid)*100:.1f}%'
            f'  ({len(wins)}胜/{len(losses)}负)')
        out(f'│  平均收益：{avg_r:>+.2f}%  │  中位数：{median:>+.2f}%')
        out(f'│  平均盈利：{avg_w:>+.2f}%  │  平均亏损：{avg_l:>+.2f}%')

        # 盈亏分布
        dist = {b: 0 for b in BUCKETS}
        for h in valid:
            dist[pct_bucket(h[key])] += 1
        out(f'│  收益分布：')
        for b in BUCKETS:
            cnt = dist[b]
            pct_share = cnt / len(valid) * 100
            bar = '█' * int(pct_share / 2)
            out(f'│    {b:>12}  {cnt:>4}笔  {pct_share:>5.1f}%  {bar}')
        out(f'└──────────────────────────────────────────────────────────────')

    # ── 明细列表（最多展示前100条） ───────────────────────────────────────────
    out()
    out('=' * 72)
    out(f'  信号明细（共 {len(all_hits)} 笔，展示全部）')
    out('=' * 72)
    hdr = (f'  {"排":>4}  {"代码":<10} {"涨停日":<12} {"D1%":>5} {"D2%":>5} {"D3%":>5}'
           f' {"买入日":<12} {"买价":>7}'
           f' {"3日%":>6} {"5日%":>6} {"7日%":>6}')
    out(hdr)
    out('  ' + '─' * 80)

    for idx, h in enumerate(all_hits, 1):
        def fmt(v): return f'{v:>+5.1f}%' if v is not None else '    --'
        out(f'  {idx:>4}  {h["code"]:<10} {fmt_date(h["lim_date"]):<12}'
            f' {h["day1_pct"]:>+4.1f}% {h["day2_pct"]:>+4.1f}% {h["day3_pct"]:>+4.1f}%'
            f' {fmt_date(h["entry_date"]):<12} {h["entry_price"]:>7.2f}'
            f' {fmt(h["fwd_3d"])} {fmt(h["fwd_5d"])} {fmt(h["fwd_7d"])}')

    out()
    out(f'  结果已保存：{OUT_FILE}')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    run()

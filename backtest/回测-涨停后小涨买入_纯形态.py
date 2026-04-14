"""
回测：涨停后连续3天小涨（且均为阳线），第四天买入（纯形态，无资金流过滤）
条件：
  Day0 : 当日涨停
  Day1~3: 每天涨幅 0% < pct ≤ 5%，且收盘 > 开盘（阳线）
  Day4 : 以当日开盘价买入
  退出 : 持有 3/5/7 个交易日后，以收盘价计算收益率

注：
  原版本曾尝试从本地 TDX eday 文件（shexday.pkg）读取超大单净值，
  经过多组已知参考值的校验（sh600089/sh600036），无法从 shexday.pkg
  的59个字段中可靠地还原 L2_AMO 超大单净值，故本版本移除该过滤条件。
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
MIN_PRICE       = 3.0
SMALL_GAIN_MIN  = 0.0
SMALL_GAIN_MAX  = 5.0
HOLD_DAYS       = [3, 5, 7]

SCAN_START = 20251001
SCAN_END   = int(datetime.now().strftime('%Y%m%d'))

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', 'output', '回测结果')
os.makedirs(OUT_DIR, exist_ok=True)
OUT_FILE = os.path.join(OUT_DIR, f'回测-涨停后小涨阳线买入_{SCAN_START}_{SCAN_END}.txt')


# ── 工具函数 ──────────────────────────────────────────────────────────────────

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


# 目标日期：4月10日
TARGET_DATE = 20260410

def get_daily_pct_on(code, target_date):
    """返回 code 在 target_date 当天的日涨跌幅（%），无数据返回 None"""
    path = os.path.join(DATA_DIRS[code[:2]], f'{code}.day')
    prev_close = None
    cur_close  = None
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32: break
                date_v, o, h, l, c = struct.unpack_from('<IIIII', chunk)
                if date_v < target_date:
                    prev_close = c / 100
                elif date_v == target_date:
                    cur_close = c / 100
                    break
                else:
                    break
    except: pass
    if cur_close is not None and prev_close and prev_close > 0:
        return round((cur_close - prev_close) / prev_close * 100, 2)
    return None


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


# ── 扫描信号 ──────────────────────────────────────────────────────────────────

def find_signals(st_codes):
    hits = []
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
            start_i = max(1, n - 250)
            for i in range(start_i, n):
                if records[i]['date'] < SCAN_START: continue
                if records[i]['date'] > SCAN_END:   break
                prev_c = records[i-1]['close']
                if not is_limit_up(code, records[i]['close'], prev_c): continue
                if records[i]['close'] < MIN_PRICE: continue

                ok = True
                day_pcts  = []
                day_dates = []
                for offset in range(1, 4):
                    j = i + offset
                    if j >= n: ok = False; break
                    prev_close = records[j-1]['close']
                    if prev_close <= 0: ok = False; break
                    pct = (records[j]['close'] - prev_close) / prev_close * 100
                    if not (SMALL_GAIN_MIN < pct <= SMALL_GAIN_MAX): ok = False; break
                    # 必须是阳线（收盘 > 开盘）
                    if records[j]['close'] <= records[j]['open']:     ok = False; break
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
                    forward[hold] = (
                        round((records[exit_idx]['close'] - entry_price) / entry_price * 100, 2)
                        if exit_idx < n else None
                    )

                hits.append({
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
        cnt = sum(1 for r in hits if r['code'][:2] == market)
        print(f'  {market.upper()} 完成，命中 {cnt} 笔', flush=True)
    return hits


# ── 统计与输出 ─────────────────────────────────────────────────────────────────

def report(all_hits):
    lines = []
    def out(s=''):
        lines.append(s); print(s)

    out('=' * 80)
    out('【回测：涨停后连续3天小涨阳线，第四天买入（纯形态）】')
    out(f'扫描区间：{fmt_date(SCAN_START)} ~ {fmt_date(SCAN_END)}')
    out(f'条件：涨停 → Day1/2/3 每天 0%<涨幅≤5% 且阳线（收>开）→ Day4开盘买入')
    out(f'价格下限：≥{MIN_PRICE}元   持仓：{HOLD_DAYS} 个交易日后收盘')
    out(f'信号总数：{len(all_hits)} 笔')
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
        for h in valid: dist[pct_bucket(h[key])] += 1
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
        f' {"D1%":>5} {"D2%":>5} {"D3%":>5}'
        f' {"买入日":<12} {"买价":>7}'
        f' {"3日%":>6} {"5日%":>6} {"7日%":>6}')
    out('  ' + '─' * 85)

    def fmt(v): return f'{v:>+5.1f}%' if v is not None else '    --'

    for idx, h in enumerate(all_hits, 1):
        out(f'  {idx:>3}  {h["code"]:<10} {fmt_date(h["lim_date"]):<12}'
            f' {h["day1_pct"]:>+4.1f}% {h["day2_pct"]:>+4.1f}% {h["day3_pct"]:>+4.1f}%'
            f' {fmt_date(h["entry_date"]):<12} {h["entry_price"]:>7.2f}'
            f' {fmt(h["fwd_3d"])} {fmt(h["fwd_5d"])} {fmt(h["fwd_7d"])}')

    # ── 按 4月10日收盘涨幅排序的副表 ──────────────────────────────────────────────
    out()
    out('=' * 80)
    out(f'  信号明细（按 {TARGET_DATE//10000}年{TARGET_DATE//100%100}月{TARGET_DATE%100}日 当日涨跌幅降序，共 {len(all_hits)} 笔）')
    out('=' * 80)
    out(f'  {"排":>3}  {"代码":<10} {"涨停日":<12}'
        f' {"D1%":>5} {"D2%":>5} {"D3%":>5}'
        f' {"买入日":<12} {"买价":>7}'
        f' {"当日%":>7}'
        f' {"3日%":>6} {"5日%":>6} {"7日%":>6}')
    out('  ' + '─' * 93)

    def get_cur(h):
        return get_daily_pct_on(h['code'], TARGET_DATE)

    # 为每笔信号算出当前涨幅
    for h in all_hits:
        h['_cur'] = get_cur(h)

    sorted_hits = sorted(all_hits,
                         key=lambda h: h['_cur'] if h['_cur'] is not None else -9999,
                         reverse=True)

    for idx, h in enumerate(sorted_hits, 1):
        cur_str = f'{h["_cur"]:>+6.1f}%' if h['_cur'] is not None else '     --'
        out(f'  {idx:>3}  {h["code"]:<10} {fmt_date(h["lim_date"]):<12}'
            f' {h["day1_pct"]:>+4.1f}% {h["day2_pct"]:>+4.1f}% {h["day3_pct"]:>+4.1f}%'
            f' {fmt_date(h["entry_date"]):<12} {h["entry_price"]:>7.2f}'
            f' {cur_str}'
            f' {fmt(h["fwd_3d"])} {fmt(h["fwd_5d"])} {fmt(h["fwd_7d"])}')

    out()
    out(f'  结果已保存：{OUT_FILE}')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


# ── 主入口 ────────────────────────────────────────────────────────────────────

def run():
    st_codes = load_st_codes()

    print('=' * 60)
    print(f'扫描本地K线，找"涨停后3天小涨阳线"形态')
    print(f'区间：{fmt_date(SCAN_START)} ~ {fmt_date(SCAN_END)}')
    print('=' * 60)

    hits = find_signals(st_codes)
    hits.sort(key=lambda x: x['lim_date'])
    print(f'\n信号共 {len(hits)} 笔')

    print()
    print('=' * 60)
    print('统计结果')
    print('=' * 60)
    report(hits)


if __name__ == '__main__':
    run()

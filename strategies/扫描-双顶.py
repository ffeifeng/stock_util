"""
双顶策略扫描

核心逻辑：
  ① 过去 LOOKBACK_DAYS 天内存在明显顶部（历史高点）
  ② 顶部附近 ±TOP_WINDOW 天内的最大成交量 = 顶部基准量
  ③ 当前价格比顶部高点低 >= DROP_MIN%（已经历充分调整，处于底部）
  ④ 近 FLAT_DAYS 天内价格波动区间 <= FLAT_RANGE%（底部横盘企稳）
  ⑤ 今天：收阳线，且成交量 > 顶部基准量（量能超越顶部，强势启动信号）

用法：
  python 扫描-双顶.py          # 扫最新一天
  python 扫描-双顶.py 1        # 往前推1天
"""
import struct, os, sys
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

DATA_DIRS = {
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
}

MIN_PRICE     = 3.0
LOOKBACK_DAYS = 120   # 往前寻找顶部的最大天数
TOP_WINDOW    = 10    # 顶部日期前后各N天内取最大成交量
DROP_MIN      = 15.0  # 当前价比顶部至少低 %（确认已充分调整）
FLAT_DAYS     = 15    # 底部横盘判断天数
FLAT_RANGE    = 10.0  # 横盘期内价格波动不超过 %

DAYS_BACK = int(sys.argv[1]) if len(sys.argv) > 1 else 0

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output', '双顶策略')


def read_day_file(path):
    records = []
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32: break
                date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
                records.append({
                    'date': date, 'open': o/100, 'high': h/100,
                    'low': l/100, 'close': c/100, 'volume': vol
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


def load_st_codes():
    st_set = set()
    p = r'D:\soft\st_codes.txt'
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                c = line.strip()
                if c: st_set.add(c)
    return st_set


def scan():
    st_codes = load_st_codes()
    results  = []
    scan_date = ''

    for market, data_dir in DATA_DIRS.items():
        if not os.path.exists(data_dir): continue
        for fname in os.listdir(data_dir):
            if not fname.endswith('.day'): continue
            code = fname[:-4]
            if not is_valid_stock(code): continue
            if code[2:] in st_codes: continue

            records = read_day_file(os.path.join(data_dir, fname))
            need = LOOKBACK_DAYS + FLAT_DAYS + TOP_WINDOW + 5 + DAYS_BACK
            if len(records) < need: continue

            i = len(records) - 1 - DAYS_BACK   # 今天索引
            today = records[i]
            yest  = records[i - 1]

            if today['close'] < MIN_PRICE: continue

            if not scan_date:
                d = str(today['date'])
                scan_date = f'{d[:4]}-{d[4:6]}-{d[6:8]}'

            # ── ① 今天必须收阳线 ─────────────────────────────────────
            if today['close'] <= today['open']:
                continue

            # ── ② 寻找顶部（顶部必须在 FLAT_DAYS+5 天之前，避免刚刚创高）──
            search_start = i - LOOKBACK_DAYS
            search_end   = i - FLAT_DAYS - 5
            if search_start < 0 or search_end <= search_start:
                continue

            peak_close = max(records[j]['close'] for j in range(search_start, search_end + 1))
            # 取最近一次达到顶部高点的日期
            peak_idx = max(j for j in range(search_start, search_end + 1)
                          if records[j]['close'] == peak_close)
            peak_date = records[peak_idx]['date']

            # ── ③ 当前价比顶部低 >= DROP_MIN% ────────────────────────
            drop_pct = (peak_close - today['close']) / peak_close * 100
            if drop_pct < DROP_MIN:
                continue

            # ── ④ 顶部附近 ±TOP_WINDOW 天内最大成交量 ────────────────
            vol_start   = max(0, peak_idx - TOP_WINDOW)
            vol_end     = min(search_end, peak_idx + TOP_WINDOW)
            top_max_vol = max(records[j]['volume'] for j in range(vol_start, vol_end + 1))
            if top_max_vol == 0:
                continue

            # ── ⑤ 今天成交量 > 顶部最大量 ───────────────────────────
            if today['volume'] <= top_max_vol:
                continue

            # ── ⑥ 底部横盘：近 FLAT_DAYS 天价格波动 <= FLAT_RANGE% ──
            flat_closes = [records[j]['close'] for j in range(i - FLAT_DAYS, i)]
            flat_high   = max(flat_closes)
            flat_low    = min(flat_closes)
            if flat_low == 0:
                continue
            flat_range_pct = (flat_high - flat_low) / flat_low * 100
            if flat_range_pct > FLAT_RANGE:
                continue

            today_pct   = (today['close'] - yest['close']) / yest['close'] * 100
            vol_ratio   = today['volume'] / top_max_vol

            results.append({
                'code':          code,
                'close':         round(today['close'], 2),
                'today_pct':     round(today_pct, 2),
                'peak_close':    round(peak_close, 2),
                'peak_date':     peak_date,
                'drop_pct':      round(drop_pct, 1),
                'top_max_vol':   round(top_max_vol / 10000, 1),
                'today_vol':     round(today['volume'] / 10000, 1),
                'vol_ratio':     round(vol_ratio, 2),
                'flat_range':    round(flat_range_pct, 1),
            })

    # ── 排序：成交量倍数越大越靠前 ────────────────────────────────────
    results.sort(key=lambda x: -x['vol_ratio'])

    # ── 输出 ──────────────────────────────────────────────────────────
    os.makedirs(OUT_DIR, exist_ok=True)
    date_tag = scan_date.replace('-', '') if scan_date else 'unknown'
    out_file = os.path.join(OUT_DIR, f'双顶扫描_{date_tag}.txt')
    lines = []

    def out(s=''):
        lines.append(s); print(s)

    out('=' * 95)
    out('【双顶策略扫描】')
    out(f'数据日期：{scan_date}    共 {len(results)} 只')
    out(f'条件：顶部回落>{DROP_MIN}%  底部横盘{FLAT_DAYS}日内振幅<{FLAT_RANGE}%  今阳线量能>顶部最大量')
    out('=' * 95)
    out(f'  {"排":>2}  {"代码":<10} {"今收":>7} {"今涨%":>7}  {"顶部价":>8} {"顶部日":>10} {"回落%":>7}  '
        f'{"顶部峰量":>9} {"今量":>9} {"倍数":>6}  {"底部振幅":>8}')
    out('  ' + '─' * 91)

    for idx, r in enumerate(results, 1):
        pd = str(r['peak_date'])
        peak_date_str = f'{pd[:4]}-{pd[4:6]}-{pd[6:]}'
        out(f'  {idx:>2}  {r["code"]:<10} {r["close"]:>7.2f} {r["today_pct"]:>+6.2f}%  '
            f'{r["peak_close"]:>8.2f}  {peak_date_str}  -{r["drop_pct"]:>5.1f}%  '
            f'{r["top_max_vol"]:>8.1f}万  {r["today_vol"]:>8.1f}万  {r["vol_ratio"]:>5.2f}x  '
            f'±{r["flat_range"]:>4.1f}%')

    out()
    out(f'  文件：{out_file}')

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print()
    if results:
        print(f'扫描完成，共 {len(results)} 只，结果已保存至：{out_file}')
    else:
        print(f'扫描完成，{scan_date} 无符合条件的股票')


if __name__ == '__main__':
    scan()

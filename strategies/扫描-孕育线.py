"""
孕育线策略扫描
  ① 近期处于下跌调整阶段（过去 DECLINE_DAYS 天内整体下跌 >= DECLINE_MIN%）
  ② 昨天：大阴线 + 明显放量
       - 跌幅 >= BIG_DROP_PCT（默认5%）
       - 成交量 >= 昨日前5日均量 * VOL_RATIO 倍（默认1.5x）
  ③ 今天：收阳线（收盘 > 开盘）
       - 成交量 <= 昨天成交量 * VOL_SHRINK（默认0.5，即缩量一半以上）

用法：
  python 扫描-孕育线.py          # 扫最新一天
  python 扫描-孕育线.py 1        # 往前推1天
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

MIN_PRICE       = 3.0
DECLINE_DAYS    = 60    # 往前看多少天计算调整幅度（仅展示，不作门槛过滤）
BIG_DROP_PCT    = 5.0   # 昨天阴线跌幅最小值（%）
VOL_RATIO       = 1.5   # 昨天成交量 >= 前5日均量 * 该倍数
VOL_SHRINK      = 0.5   # 今天成交量 <= 昨天成交量 * 该比例
PRE_TREND_DAYS  = 10    # 大阴线前N天内不能有明显反弹
REBOUND_MAX     = 0.03  # 大阴线前1天相比N天前最多涨3%（超过视为已反弹）

DAYS_BACK = int(sys.argv[1]) if len(sys.argv) > 1 else 0

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output', '孕育线策略')


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
            need = 2 + DECLINE_DAYS + 5 + PRE_TREND_DAYS + DAYS_BACK
            if len(records) < need: continue

            i     = len(records) - 1 - DAYS_BACK   # 今天
            i_y   = i - 1                           # 昨天（大阴线日）
            i_y5s = i_y - 5                         # 昨天的前5日起点

            today  = records[i]
            yest   = records[i_y]

            if today['close'] < MIN_PRICE: continue

            if not scan_date:
                d = str(today['date'])
                scan_date = f'{d[:4]}-{d[4:6]}-{d[6:8]}'

            # ── ① 今天收阳线 ─────────────────────────────────────────
            if today['close'] <= today['open']:
                continue

            # ── ② 今天成交量 <= 昨天 * VOL_SHRINK ────────────────────
            if yest['volume'] == 0: continue
            vol_ratio_today = today['volume'] / yest['volume']
            if vol_ratio_today > VOL_SHRINK:
                continue

            # ── ③ 昨天大阴线 ─────────────────────────────────────────
            if yest['close'] >= yest['open']:   # 昨天必须是阴线
                continue
            ref_close = records[i_y - 1]['close']
            if ref_close == 0: continue
            yest_drop = (ref_close - yest['close']) / ref_close * 100
            if yest_drop < BIG_DROP_PCT:
                continue

            # ── ④ 昨天放量（>= 前5日均量 * VOL_RATIO）──────────────
            vol5 = [records[j]['volume'] for j in range(i_y5s, i_y5s + 5)]
            avg5 = sum(vol5) / 5 if vol5 else 0
            if avg5 == 0: continue
            yest_vol_ratio = yest['volume'] / avg5
            if yest_vol_ratio < VOL_RATIO:
                continue

            # ── ⑤ 大阴线前不能有明显反弹（仍需处于下跌趋势中）──────────
            pre_ref = records[i_y - 1 - PRE_TREND_DAYS]['close']   # 大阴线前N+1天收盘
            pre_now = records[i_y - 1]['close']                     # 大阴线前1天收盘
            if pre_ref > 0 and pre_now > pre_ref * (1 + REBOUND_MAX):
                continue   # 已经反弹超过3%，排除

            # ── ⑥ 计算近期调整幅度（仅展示，不过滤）──────────────────
            start = max(0, i_y - DECLINE_DAYS)
            lookback = [records[j]['high'] for j in range(start, i_y)]
            period_high = max(lookback) if lookback else yest['close']
            decline_pct = (period_high - yest['close']) / period_high * 100 if period_high else 0

            # ── 计算今天涨幅 ─────────────────────────────────────────
            today_pct = (today['close'] - yest['close']) / yest['close'] * 100

            results.append({
                'code':           code,
                'close':          round(today['close'], 2),
                'open':           round(today['open'], 2),
                'today_pct':      round(today_pct, 2),
                'yest_close':     round(yest['close'], 2),
                'yest_drop':      round(yest_drop, 2),
                'yest_vol':       round(yest['volume'] / 10000, 1),
                'yest_vol_ratio': round(yest_vol_ratio, 1),
                'today_vol':      round(today['volume'] / 10000, 1),
                'vol_ratio_today':round(vol_ratio_today, 2),
                'decline_pct':    round(decline_pct, 1),
            })

    # ── 排序：成交量比越小越靠前（缩量越明显越好）────────────────────
    results.sort(key=lambda x: x['vol_ratio_today'])

    # ── 输出 ──────────────────────────────────────────────────────────
    os.makedirs(OUT_DIR, exist_ok=True)
    date_tag = scan_date.replace('-', '') if scan_date else 'unknown'
    OUT_FILE = os.path.join(OUT_DIR, f'孕育线扫描_{date_tag}.txt')
    lines = []

    def out(s=''):
        lines.append(s); print(s)

    d = scan_date or '未知日期'
    out('=' * 90)
    out(f'【孕育线策略扫描】')
    out(f'数据日期：{d}    共 {len(results)} 只')
    out(f'条件：昨阴线跌>{BIG_DROP_PCT}%且放量>{VOL_RATIO}x均量  今阳线且缩量<{int(VOL_SHRINK*100)}%  大阴线前{PRE_TREND_DAYS}日内无反弹>{int(REBOUND_MAX*100)}%')
    out('=' * 90)
    out(f'  {"排":>2}  {"代码":<10} {"今收":>7} {"今涨%":>7}  {"昨收":>7} {"昨跌%":>7} {"昨量(万)":>9} {"昨量比":>6}  {"今量(万)":>9} {"缩量比":>6}  {"调整幅":>7}')
    out('  ' + '─' * 86)

    for idx, r in enumerate(results, 1):
        out(f'  {idx:>2}  {r["code"]:<10} {r["close"]:>7.2f} {r["today_pct"]:>+6.2f}%  '
            f'{r["yest_close"]:>7.2f} {-r["yest_drop"]:>+6.2f}%  '
            f'{r["yest_vol"]:>8.1f}万  {r["yest_vol_ratio"]:>4.1f}x  '
            f'{r["today_vol"]:>8.1f}万  {r["vol_ratio_today"]:>5.2f}x  '
            f'-{r["decline_pct"]:>5.1f}%')

    out()
    out(f'  文件：{OUT_FILE}')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print()
    if results:
        print(f'扫描完成，共 {len(results)} 只，结果已保存至：{OUT_FILE}')
    else:
        print(f'扫描完成，{scan_date} 无符合条件的股票')


if __name__ == '__main__':
    scan()

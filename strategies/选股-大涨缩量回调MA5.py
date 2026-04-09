"""
策略：放量大阳线后缩量阴线回调
形态描述：
  1. 前1/2/3天出现放量大阳线（涨幅 >= SURGE_MIN_PCT，量 >= 前20日均量 SURGE_VOL_MULT 倍）
  2. 今天是阴线（收 < 开）
  3. 今天的成交量 < 大阳线成交量 * YIN_SHRINK（缩量，说明无抛压）
  4. 今天 MA5 > MA10 > MA30（多头排列，趋势向上）

逻辑：大阳线代表主力主动拉升，阴线缩量回调是自然换手，是低风险介入点。

用法：
  python 选股-大涨缩量回调MA5.py [开始日期] [结束日期]
  python 选股-大涨缩量回调MA5.py 20260201 20260313
"""

import struct
import os
import sys
from datetime import datetime, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ── 数据路径 ──────────────────────────────────────────────────────────────────
DATA_DIRS = {
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
}

# ── 策略参数 ──────────────────────────────────────────────────────────────────
SURGE_MIN_PCT     = 7.0   # 大阳线最低涨幅（%），相对前一日收盘
SURGE_VOL_MULT    = 2.0   # 大阳线量 >= 前20日均量 * 此倍数（放量确认）
MAX_YANG_LOOKBACK = 3     # 往前最多找几天内的大阳线（1/2/3天前）
YIN_SHRINK        = 0.60  # 信号日（阴线）量 < 大阳线量 * 此比例（缩量门槛）
MIN_PRICE         = 3.0   # 最低股价（元）

# ── 后续跟踪天数 ───────────────────────────────────────────────────────────────
TRACK_DAYS        = [1, 2, 3]
CAPITAL_PER_TRADE = 50000   # 每笔模拟资金（元）


def read_day_file(filepath):
    records = []
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32:
                    break
                date, open_, high, low, close, amount, volume, _ = \
                    struct.unpack('<IIIIIfII', chunk)
                records.append({
                    'date':   date,
                    'open':   open_  / 100.0,
                    'high':   high   / 100.0,
                    'low':    low    / 100.0,
                    'close':  close  / 100.0,
                    'volume': volume,
                })
    except Exception:
        pass
    return records


def calc_ma(values, n):
    result = [None] * len(values)
    for i in range(n - 1, len(values)):
        result[i] = sum(values[i - n + 1:i + 1]) / n
    return result


def is_valid_stock(code):
    c = code.lower()
    if c.startswith('bj'):
        return False
    num = c[2:]
    if c.startswith('sh'):
        return num[:3] in ['600', '601', '602', '603', '604', '605', '688']
    if c.startswith('sz'):
        return num[:3] in ['000', '001', '002', '003', '300', '301']
    return False


def load_st_codes():
    st_file = r'D:\soft\st_codes.txt'
    st_set = set()
    if os.path.exists(st_file):
        with open(st_file, 'r') as f:
            for line in f:
                code = line.strip()
                if code:
                    st_set.add(code)
    return st_set


def check_stock(records, scan_start, scan_end):
    if len(records) < 60:
        return []

    closes   = [r['close']  for r in records]
    volumes  = [r['volume'] for r in records]
    ma5      = calc_ma(closes,  5)
    ma10     = calc_ma(closes, 10)
    ma30     = calc_ma(closes, 30)
    ma60     = calc_ma(closes, 60)
    vol_ma20 = calc_ma(volumes, 20)

    hits = []

    for si in range(30, len(records)):
        sig_date  = records[si]['date']
        if sig_date < scan_start or sig_date > scan_end:
            continue

        sig_open  = records[si]['open']
        sig_close = records[si]['close']
        sig_vol   = volumes[si]

        # ── 信号日必须是阴线 ─────────────────────────────────────────────────
        if sig_close >= sig_open:
            continue
        if sig_close < MIN_PRICE:
            continue

        # ── MA5 > MA10 > MA30 多头排列（信号日） ────────────────────────────
        if (ma5[si] is None or ma10[si] is None or ma30[si] is None):
            continue
        if not (ma5[si] > ma10[si] > ma30[si]):
            continue

        # ── 往前 1~3 天找放量大阳线 ──────────────────────────────────────────
        yang_hit = None
        for lookback in range(1, MAX_YANG_LOOKBACK + 1):
            bi = si - lookback
            if bi < 21:
                break
            if vol_ma20[bi] is None:
                break

            b_open  = records[bi]['open']
            b_close = records[bi]['close']
            b_vol   = volumes[bi]

            # 必须是阳线
            if b_close <= b_open:
                continue

            # 涨幅检验（相对前一日收盘）
            prev_close = records[bi - 1]['close']
            if prev_close == 0:
                break
            surge_pct = (b_close - prev_close) / prev_close * 100
            if surge_pct < SURGE_MIN_PCT:
                continue

            # 放量检验
            if b_vol < vol_ma20[bi] * SURGE_VOL_MULT:
                continue

            # 信号日缩量：阴线量 < 大阳线量 * YIN_SHRINK
            if sig_vol >= b_vol * YIN_SHRINK:
                continue

            yang_hit = {
                'bi': bi,
                'lookback': lookback,
                'surge_pct': round(surge_pct, 2),
                'surge_vol_mult': round(b_vol / vol_ma20[bi], 2),
                'surge_date': records[bi]['date'],
                'surge_close': round(b_close, 2),
                'vol_ratio': round(sig_vol / b_vol, 2),  # 阴线量/大阳线量
            }
            break   # 取最近的一根大阳线

        if yang_hit is None:
            continue

        # ── 后续跟踪收益 ─────────────────────────────────────────────────────
        entry_price = sig_close
        forward = {'entry_close': round(entry_price, 2)}
        for n in TRACK_DAYS:
            exit_idx = si + n
            if exit_idx < len(records) and entry_price > 0:
                forward[f'fwd_{n}d_pct'] = round(
                    (records[exit_idx]['close'] - entry_price) / entry_price * 100, 2)
            else:
                forward[f'fwd_{n}d_pct'] = None

        # ── MA5 止损追踪（跌破MA5收盘卖出）──────────────────────────────────
        ma5_exit_price = None
        ma5_exit_date  = None
        ma5_hold_days  = None
        ma5_still_hold = False
        max_fwd = min(si + 61, len(records))
        for j in range(si + 1, max_fwd):
            if ma5[j] is not None and records[j]['close'] < ma5[j]:
                ma5_exit_price = records[j]['close']
                ma5_exit_date  = records[j]['date']
                ma5_hold_days  = j - si
                break
        if ma5_exit_price is None:
            last_j = max_fwd - 1
            ma5_exit_price = records[last_j]['close']
            ma5_exit_date  = records[last_j]['date']
            ma5_hold_days  = last_j - si
            ma5_still_hold = True

        ma5_exit_pct = round(
            (ma5_exit_price - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0
        shares     = int(CAPITAL_PER_TRADE / entry_price / 100) * 100
        ma5_profit = round(shares * (ma5_exit_price - entry_price), 2)

        # 信号日阴线回调幅度（相对大阳线收盘）
        pb_pct = (sig_close - yang_hit['surge_close']) / yang_hit['surge_close'] * 100

        hits.append({
            'signal_date':    sig_date,
            'signal_close':   round(sig_close, 2),
            'signal_open':    round(sig_open, 2),
            'pb_pct':         round(pb_pct, 2),       # 信号日相对大阳线收盘的涨跌幅
            'vol_ratio':      yang_hit['vol_ratio'],   # 阴线量/大阳线量
            'ma5':            round(ma5[si], 2),
            'ma10':           round(ma10[si], 2),
            'ma30':           round(ma30[si], 2),
            'surge_date':     yang_hit['surge_date'],
            'surge_close':    yang_hit['surge_close'],
            'surge_pct':      yang_hit['surge_pct'],
            'surge_vol_mult': yang_hit['surge_vol_mult'],
            'lookback':       yang_hit['lookback'],    # 大阳线在几天前
            **forward,
            'ma5_exit_date':  ma5_exit_date,
            'ma5_exit_price': round(ma5_exit_price, 2),
            'ma5_exit_pct':   ma5_exit_pct,
            'ma5_hold_days':  ma5_hold_days,
            'ma5_still_hold': ma5_still_hold,
            'shares':         shares,
            'ma5_profit':     ma5_profit,
        })

    return hits


def get_recent_trading_days(n=20):
    end   = datetime.now()
    start = end - timedelta(days=n + 16)
    return int(start.strftime('%Y%m%d')), int(end.strftime('%Y%m%d'))


def main():
    if len(sys.argv) >= 3:
        try:
            scan_start = int(sys.argv[1])
            scan_end   = int(sys.argv[2])
        except ValueError:
            scan_start, scan_end = get_recent_trading_days(20)
    else:
        scan_start, scan_end = get_recent_trading_days(20)

    st_codes = load_st_codes()

    all_results = []
    for market, data_dir in DATA_DIRS.items():
        if not os.path.exists(data_dir):
            continue
        files = [f for f in os.listdir(data_dir) if f.endswith('.day')]
        valid = [f for f in files
                 if is_valid_stock(f[:-4]) and f[2:-4] not in st_codes]
        print(f'扫描 {market.upper()} 市场：{len(valid)} 只...')
        for fname in valid:
            code    = fname[:-4]
            records = read_day_file(os.path.join(data_dir, fname))
            hits    = check_stock(records, scan_start, scan_end)
            for h in hits:
                h['code'] = code
                all_results.append(h)

    all_results.sort(key=lambda x: (x['signal_date'], -x['surge_pct']))

    # 去重（同一只股票同一根大阳线只取最近一次阴线信号）
    seen_key = set()
    dedup = []
    for r in all_results:
        k = (r['code'], r['surge_date'])
        if k not in seen_key:
            seen_key.add(k)
            dedup.append(r)

    ts      = datetime.now().strftime('%Y%m%d_%H%M')
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
    os.makedirs(out_dir, exist_ok=True)
    txt_path = os.path.join(out_dir, f'大涨缩量MA5_{ts}.txt')

    lines = []
    def out(s=''):
        lines.append(s)
        print(s)

    out('=' * 108)
    out(f'【大阳线后缩量阴线回调】  扫描区间：{scan_start} - {scan_end}')
    out(f'共找到 {len(all_results)} 个信号（去重后 {len(dedup)} 笔）   扫描时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}')
    out(f'参数：大阳线>={SURGE_MIN_PCT}%  量>={SURGE_VOL_MULT}x均量  阴线量<大阳线{YIN_SHRINK*100:.0f}%  MA5>MA10>MA30')
    out('=' * 108)
    out(f'  {"排":>2}  {"代码":<10} {"阴线日(信号)":<14} {"回调%":>6} {"缩量":>5}  '
        f'{"大阳日":<12} {"大阳%":>6} {"量倍":>5} {"前N天":>4}  '
        f'{"1日%":>6} {"2日%":>6} {"3日%":>6}  {"MA5止损"}')
    out('  ' + '─' * 106)

    for i, r in enumerate(dedup, 1):
        sd = str(r['signal_date'])
        bd = str(r['surge_date'])
        f1 = f'{r["fwd_1d_pct"]:>+5.1f}%' if r['fwd_1d_pct'] is not None else '    --'
        f2 = f'{r["fwd_2d_pct"]:>+5.1f}%' if r['fwd_2d_pct'] is not None else '    --'
        f3 = f'{r["fwd_3d_pct"]:>+5.1f}%' if r['fwd_3d_pct'] is not None else '    --'
        if r['ma5_still_hold']:
            ma5s = f'持有中 ({r["ma5_exit_pct"]:>+.1f}%)'
        else:
            tag  = '盈' if r['ma5_exit_pct'] > 0 else '损'
            ma5s = f'MA5{tag} {r["ma5_exit_pct"]:>+.1f}% / {r["ma5_hold_days"]}天'

        out(f'  {i:>2}  {r["code"]:<10} '
            f'{sd[:4]}-{sd[4:6]}-{sd[6:]}  '
            f'{r["pb_pct"]:>+5.1f}%  {r["vol_ratio"]:>4.2f}x  '
            f'{bd[:4]}-{bd[4:6]}-{bd[6:]}  '
            f'{r["surge_pct"]:>5.1f}%  {r["surge_vol_mult"]:>4.1f}x  '
            f'{r["lookback"]:>2}天前  '
            f'{f1} {f2} {f3}  {ma5s}')

    # ── 胜率统计 ─────────────────────────────────────────────────────────────
    out()
    out('=' * 60)
    out('  胜率统计  （入场：信号日收盘  退出：持有N日收盘）')
    out('=' * 60)
    for n in TRACK_DAYS:
        key     = f'fwd_{n}d_pct'
        valid_r = [r for r in dedup if r[key] is not None]
        if not valid_r:
            continue
        win     = sum(1 for r in valid_r if r[key] > 0)
        avg_r   = sum(r[key] for r in valid_r) / len(valid_r)
        avg_win = sum(r[key] for r in valid_r if r[key] > 0) / max(win, 1)
        loss_r  = [r for r in valid_r if r[key] <= 0]
        avg_los = sum(r[key] for r in loss_r) / max(len(loss_r), 1)
        out(f'  持有{n:>2}日  总信号:{len(valid_r):>4}  '
            f'胜率:{win/len(valid_r)*100:>5.1f}%({win}/{len(valid_r)})  '
            f'平均:{avg_r:>+6.2f}%  '
            f'平均盈:{avg_win:>+6.2f}%  平均亏:{avg_los:>+6.2f}%')

    # ── MA5止损汇总 ───────────────────────────────────────────────────────────
    total_profit  = sum(r['ma5_profit'] for r in dedup)
    total_capital = len(dedup) * CAPITAL_PER_TRADE
    closed        = [r for r in dedup if not r['ma5_still_hold']]
    win_list      = [r for r in closed if r['ma5_exit_pct'] > 0]
    out()
    out('=' * 60)
    out(f'  MA5止损汇总  |  每笔{CAPITAL_PER_TRADE//10000}万  |  共{len(dedup)}笔')
    out('=' * 60)
    if total_capital > 0:
        out(f'  总投入：{total_capital/10000:.1f}万   总盈亏：{total_profit:>+.0f}元 '
            f'({total_profit/total_capital*100:>+.2f}%)')
    if closed:
        out(f'  已结清：{len(closed)}笔  胜率：{len(win_list)/len(closed)*100:.1f}%'
            f'（{len(win_list)}胜/{len(closed)-len(win_list)}负）  '
            f'持有中：{len(dedup)-len(closed)}笔')
        avg_cl = sum(r['ma5_exit_pct'] for r in closed) / len(closed)
        out(f'  已结清均收益：{avg_cl:>+.2f}%')

    out()
    out(f'结果已保存：{txt_path}')

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    main()

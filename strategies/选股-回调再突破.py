"""
选股脚本：主升浪回调再突破
形态：近期有明显主升浪(20%+) + 缩量有序回调(5%~35%) + 再次站上 MA30
区别于起爆点（长期横盘突破），本策略针对"先拉后洗再突破"强势股
用法：python 选股-回调再突破.py [开始日期] [结束日期]
输出：D:\soft\选股结果-回调再突破.json
"""

import struct, os, sys
from datetime import datetime, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

DATA_DIRS = {
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
}
CW_DIR = r'D:\soft\new_tdx\vipdoc\cw'


def load_cw_indicator(code, indicator_id=11):
    """读取通达信 cw 目录中某只股票的指定指标（默认 ID=11 超大单）
    v1 = 超大单买入额(万元), v2 = 超大单卖出额(万元)
    返回 {date_int(YYYYMMDD): net(万元)} 字典，净流入 = v1 - v2
    """
    import math
    market = code[:2]
    stock  = code[2:]
    path   = os.path.join(CW_DIR, f'gp{market}{stock}.dat')
    if not os.path.exists(path):
        return {}
    result = {}
    RSIZE  = 13
    try:
        with open(path, 'rb') as f:
            raw = f.read()
        for i in range(len(raw) // RSIZE):
            chunk = raw[i*RSIZE : i*RSIZE+RSIZE]
            if chunk[0] != indicator_id:
                continue
            date_int = struct.unpack('<I', chunk[1:5])[0]
            yr = date_int // 10000
            mo = (date_int % 10000) // 100
            dy = date_int % 100
            if not (1990 <= yr <= 2030 and 1 <= mo <= 12 and 1 <= dy <= 31):
                continue
            v1 = struct.unpack('<f', chunk[5:9])[0]
            v2 = struct.unpack('<f', chunk[9:13])[0]
            if math.isfinite(v1) and math.isfinite(v2):
                result[date_int] = round(v1 - v2, 2)   # 净流入 = 买入 - 卖出（万元）
    except Exception:
        pass
    return result


def calc_inflow_stats(cw_data, start_date, end_date):
    """统计某日期区间内超大单净流入情况
    返回 (净流入天数, 有数据总天数, 累计净流入亿元)
    """
    relevant = {d: v for d, v in cw_data.items() if start_date <= d <= end_date}
    if not relevant:
        return 0, 0, 0.0
    in_days = sum(1 for v in relevant.values() if v > 0)
    total   = len(relevant)
    net_yi  = round(sum(relevant.values()) / 10000, 2)  # 万元 → 亿元
    return in_days, total, net_yi

# ─── 策略参数 ───────────────────────────────────────────────
SURGE_MIN_PCT     = 20.0   # 主升浪最小涨幅 %（从起点到峰值）
SURGE_MIN_DAYS    = 5      # 主升浪起点到峰值最短天数
SURGE_MAX_DAYS    = 80     # 主升浪起点到峰值最长天数（太慢的不算急涨）
PULLBACK_MIN_PCT  = 5.0    # 回调最小幅度 %（太浅说明没洗盘）
PULLBACK_MAX_PCT  = 35.0   # 回调最大幅度 %（超过则主力可能出局）
PULLBACK_MIN_DAYS = 8      # 回调最短持续天数
PULLBACK_MAX_DAYS = 50     # 回调最长持续天数
SHRINK_RATIO      = 0.80   # 回调期均量 / 主升期均量（要求缩量）
RETRACE_MAX       = 0.618  # 斐波那契：回调不超过主升幅度的 61.8%
MIN_PRICE         = 3.0    # 最低股价
# ────────────────────────────────────────────────────────────


def get_recent_trading_days(n=20):
    """最近 n 个交易日（默认 20 天）"""
    end = datetime.now()
    start = end - timedelta(days=n + 16)
    return int(start.strftime('%Y%m%d')), int(end.strftime('%Y%m%d'))


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
                    'date': date, 'open': open_/100, 'high': high/100,
                    'low': low/100, 'close': close/100, 'volume': volume,
                })
    except Exception:
        pass
    return records


def calc_ma(values, n):
    return [None if i < n-1 else sum(values[i-n+1:i+1])/n
            for i in range(len(values))]


def find_breakout_day(records, ma30, start_date, end_date):
    """找收盘穿越 MA30 的日期，且后续至少 1 天确认（避免假突破）"""
    for i in range(1, len(records)):
        date = records[i]['date']
        if date < start_date or date > end_date:
            continue
        if ma30[i] is None or ma30[i-1] is None:
            continue
        if not (records[i-1]['close'] <= ma30[i-1] and
                records[i]['close'] > ma30[i]):
            continue
        for j in range(i+1, min(i+4, len(records))):
            if ma30[j] and records[j]['close'] > ma30[j]:
                return i
    return -1


def check_stock(records, break_start, break_end, code=''):
    if len(records) < 120:
        return None

    closes  = [r['close'] for r in records]
    volumes = [r['volume'] for r in records]
    ma5  = calc_ma(closes, 5)
    ma20 = calc_ma(closes, 20)
    ma30 = calc_ma(closes, 30)
    ma60 = calc_ma(closes, 60)

    bi = find_breakout_day(records, ma30, break_start, break_end)
    if bi < 60:
        return None

    break_close = records[bi]['close']
    break_ma30  = ma30[bi]
    break_date  = records[bi]['date']

    # ── 突破前连续在 MA30 下方不超过 3 天（快速回拉才是强势信号）
    # 在均线下方拖沓 4+ 天 = 主力护盘意愿弱，排除
    days_below_ma30 = 0
    for k in range(bi - 1, max(bi - 10, -1), -1):
        if ma30[k] is None or records[k]['close'] >= ma30[k]:
            break
        days_below_ma30 += 1
    if days_below_ma30 > 3:
        return None

    if break_close < MIN_PRICE:
        return None

    break_pct = (break_close - break_ma30) / break_ma30 * 100
    if break_pct < 0.3 or break_pct > 15:
        return None

    # ── Step1：找主升浪峰值 ──────────────────────────────────
    # 在突破日之前 10~(SURGE_MAX_DAYS + PULLBACK_MAX_DAYS) 天内找最高点
    peak_search_start = max(0, bi - SURGE_MAX_DAYS - PULLBACK_MAX_DAYS)
    peak_search_end   = bi - 2   # 峰值至少在突破日前2天
    if peak_search_end <= peak_search_start:
        return None

    peak_local = max(range(peak_search_end - peak_search_start + 1),
                     key=lambda k: closes[peak_search_start + k])
    peak_idx   = peak_search_start + peak_local
    peak_close = closes[peak_idx]
    peak_date  = records[peak_idx]['date']

    # ── Step2：找回调低点（峰值之后到突破日前）────────────────
    if peak_idx >= bi - 1:
        return None
    pb_slice = closes[peak_idx + 1:bi]   # 峰值后、突破日前
    if not pb_slice:
        return None

    pb_local  = min(range(len(pb_slice)), key=lambda k: pb_slice[k])
    pb_idx    = peak_idx + 1 + pb_local
    pb_close  = closes[pb_idx]
    pb_date   = records[pb_idx]['date']

    # 回调幅度
    pb_pct = (peak_close - pb_close) / peak_close * 100
    if pb_pct < PULLBACK_MIN_PCT or pb_pct > PULLBACK_MAX_PCT:
        return None

    # 回调持续天数（峰值到低点）
    pullback_days = pb_idx - peak_idx
    if pullback_days < PULLBACK_MIN_DAYS or pullback_days > PULLBACK_MAX_DAYS:
        return None

    # ── Step3：找主升浪起点（峰值之前）──────────────────────
    base_search_start = max(0, peak_idx - SURGE_MAX_DAYS)
    base_search_end   = max(0, peak_idx - SURGE_MIN_DAYS)
    if base_search_end <= base_search_start:
        return None

    base_slice = closes[base_search_start:base_search_end + 1]
    base_local = min(range(len(base_slice)), key=lambda k: base_slice[k])
    base_idx   = base_search_start + base_local
    base_close = closes[base_idx]
    base_date  = records[base_idx]['date']

    # 主升浪涨幅
    if base_close <= 0:
        return None
    surge_pct = (peak_close - base_close) / base_close * 100
    if surge_pct < SURGE_MIN_PCT:
        return None

    # 主升浪必须在峰值之前，且逻辑一致
    if base_idx >= peak_idx:
        return None

    # 回调低点不得低于主升浪起点的 110%（否则视为行情完全打回）
    if pb_close < base_close * 1.10:
        return None

    # 斐波那契回撤：回调幅度不超过主升幅度 61.8%
    surge_amplitude = peak_close - base_close
    retraced        = peak_close - pb_close
    retrace_ratio   = retraced / surge_amplitude if surge_amplitude > 0 else 1.0
    if retrace_ratio > RETRACE_MAX:
        return None

    # ── Step4：量能对比 ──────────────────────────────────────
    # 主升期量能：只取峰值前最近 20 个交易日的均量
    # 避免起点选得过早（含横盘期）导致均量被稀释，无法真实反映拉升热度
    surge_vol_start = max(base_idx, peak_idx - 20)
    surge_vols      = volumes[surge_vol_start:peak_idx + 1]
    pullback_vols   = volumes[peak_idx + 1:pb_idx + 1]
    if not surge_vols or not pullback_vols:
        return None

    avg_vol_surge    = sum(surge_vols)    / len(surge_vols)
    avg_vol_pullback = sum(pullback_vols) / len(pullback_vols)
    if avg_vol_surge == 0:
        return None

    shrink = avg_vol_pullback / avg_vol_surge
    if shrink > SHRINK_RATIO:
        return None

    # ── Step5：突破日 MA 多头排列 ────────────────────────────
    bull_ma = (ma5[bi] and ma20[bi] and ma60[bi] and
               ma5[bi] > ma20[bi] and ma20[bi] > ma60[bi])

    # ── Step6：当前仍在 MA30 上方 ────────────────────────────
    if ma30[-1] is None or records[-1]['close'] < ma30[-1]:
        return None

    # ── Step7：回调期 MA30 不能持续下行超 8% ────────────────────
    # 回调期 MA30 大幅下行 = 中期趋势向下（主力出货），而非正常洗盘
    if ma30[peak_idx] and ma30[pb_idx]:
        ma30_drop_pct = (ma30[peak_idx] - ma30[pb_idx]) / ma30[peak_idx] * 100
        if ma30_drop_pct > 8.0:
            return None

    # ── Step8：当前价格不能超过突破价 5%（超过则已大幅上涨，无需追高）
    current_close = records[-1]['close']
    current_vs_break = (current_close - break_close) / break_close * 100
    if current_close > break_close * 1.05:
        return None

    # ── 突破后状态 ────────────────────────────────────────────
    post = records[bi + 1:]
    hold_break = all(r['close'] >= break_close for r in post)
    post_high  = max(r['close'] for r in post) if post else break_close
    post_gain  = (post_high - break_close) / break_close * 100

    pullback_date2  = None
    pullback_close2 = None
    restable_date   = None
    if post:
        pb2_idx = min(range(len(post)), key=lambda k: post[k]['close'])
        pullback_date2  = post[pb2_idx]['date']
        pullback_close2 = round(post[pb2_idx]['close'], 2)
        for j in range(bi + 1 + pb2_idx + 1, len(records)):
            if records[j]['close'] >= break_close:
                restable_date = records[j]['date']
                break
        if hold_break:
            restable_date = None

    def fmt(d):
        s = str(d); return f'{s[:4]}-{s[4:6]}-{s[6:]}'

    # ── 超大单净流入统计（ID=11）────────────────────────────────
    # 回调（洗盘）区间：主升峰值次日 → 回调低点
    # 突破后区间：突破日 → 最新一日
    cw_data = load_cw_indicator(code, indicator_id=11) if code else {}
    pb_d_start = records[peak_idx]['date']
    pb_d_end   = records[pb_idx]['date']
    today_d    = records[-1]['date']
    w_in, w_tot, w_net = calc_inflow_stats(cw_data, pb_d_start, pb_d_end)
    a_in, a_tot, a_net = calc_inflow_stats(cw_data, break_date,  today_d)

    return {
        'break_date':     break_date,
        'break_close':    round(break_close, 2),
        'break_ma30':     round(break_ma30, 2),
        'break_pct':      round(break_pct, 2),
        'base_date':      base_date,
        'base_close':     round(base_close, 2),
        'peak_date':      peak_date,
        'peak_close':     round(peak_close, 2),
        'surge_pct':      round(surge_pct, 2),
        'surge_days':     peak_idx - base_idx,
        'pb_date':        pb_date,
        'pb_close':       round(pb_close, 2),
        'pb_pct':         round(pb_pct, 2),
        'pullback_days':  pullback_days,
        'shrink_ratio':   round(shrink, 2),
        'retrace_ratio':  round(retrace_ratio, 3),
        'bull_ma':        bull_ma,
        'hold_break':     hold_break,
        'pullback_date':  fmt(pullback_date2) if pullback_date2 else None,
        'pullback_close': pullback_close2,
        'restable_date':  fmt(restable_date) if restable_date else None,
        'post_gain':      round(post_gain, 2),
        'wash_inflow_days':  w_in,
        'wash_total_days':   w_tot,
        'wash_net_yi':       w_net,
        'after_inflow_days': a_in,
        'after_total_days':  a_tot,
        'after_net_yi':      a_net,
        'current_close':       round(current_close, 2),
        'current_vs_break':    round(current_vs_break, 1),
        'days_below_ma30':     days_below_ma30,
    }


def score(r):
    s = 0
    # 主升浪涨幅（上限封顶）
    s += min(r['surge_pct'], 80) * 0.25
    # 缩量得分
    s += (1 - r['shrink_ratio']) * 25
    # 回调幅度：10~20% 最佳（自然换手）
    pb = r['pb_pct']
    if   10 <= pb <= 20:  s += 15
    elif 7  <= pb < 10 or 20 < pb <= 28: s += 8
    # 回调天数：15~35天最佳
    pd = r['pullback_days']
    if   15 <= pd <= 35:  s += 10
    elif 8  <= pd < 15 or 35 < pd <= 50: s += 5
    # 斐波那契回撤 < 38.2% 强加分
    rr = r.get('retrace_ratio', 1.0)
    if   rr < 0.382: s += 12
    elif rr < 0.500: s += 6
    # MA 多头排列
    if r.get('bull_ma'):   s += 8
    # 突破后守住突破价
    if r.get('hold_break'): s += 10
    # 温和突破（1%~5%）
    if 1 <= r['break_pct'] <= 5: s += 5
    return round(s, 1)


def is_valid_stock(code):
    c   = code.lower()
    num = c[2:]
    if c.startswith('bj'): return False
    if c.startswith('sh'): return num[:3] in ['600','601','602','603','604','605','688']
    if c.startswith('sz'): return num[:3] in ['000','001','002','003','300','301']
    return False


def load_st_codes():
    st_set = set()
    st_file = r'D:\soft\st_codes.txt'
    if os.path.exists(st_file):
        with open(st_file, 'r') as f:
            for line in f:
                code = line.strip()
                if code: st_set.add(code)
    return st_set


def main():
    if len(sys.argv) >= 3:
        try:
            break_start = int(sys.argv[1])
            break_end   = int(sys.argv[2])
        except ValueError:
            break_start, break_end = get_recent_trading_days()
    else:
        break_start, break_end = get_recent_trading_days()

    st_codes = load_st_codes()
    results  = []

    for market, data_dir in DATA_DIRS.items():
        if not os.path.exists(data_dir): continue
        for filename in os.listdir(data_dir):
            if not filename.endswith('.day'): continue
            code = filename.replace('.day', '')
            if not is_valid_stock(code): continue
            if code[2:] in st_codes: continue
            records = read_day_file(os.path.join(data_dir, filename))
            hit = check_stock(records, break_start, break_end, code=code)
            if hit:
                hit['code']  = code
                hit['score'] = score(hit)
                results.append(hit)

    results.sort(key=lambda x: x['score'], reverse=True)

    def fmt(d):
        if d is None: return None
        s = str(d); return f'{s[:4]}-{s[4:6]}-{s[6:]}'

    ts       = datetime.now().strftime('%Y%m%d_%H%M')
    out_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
    os.makedirs(out_dir, exist_ok=True)
    txt_path = os.path.join(out_dir, f'回调再突破_{ts}.txt')

    lines = []
    def out(s=''):
        lines.append(s)
        print(s)

    out('=' * 88)
    out(f'【回调再突破】  扫描区间：{break_start} - {break_end}')
    out(f'共找到 {len(results)} 只候选   扫描时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}')
    out(f'参数：主升>={SURGE_MIN_PCT}%  回调{PULLBACK_MIN_PCT}~{PULLBACK_MAX_PCT}%  '
        f'回调{PULLBACK_MIN_DAYS}~{PULLBACK_MAX_DAYS}天  缩量<{SHRINK_RATIO}x  斐波<{RETRACE_MAX*100:.0f}%')
    out('=' * 88)
    out(f'  {"排":>2}  {"代码":<10} {"评分":>5}  {"突破日":<12} {"突破价":>7} {"超MA30":>6}  '
        f'{"主升涨":>6}/{"天":>2}  {"回调":>5}/{"天":>2}  {"斐波":>5} {"缩量":>5}  {"状态":<7}  {"回踩→企稳"}')
    out('  ' + '─' * 88)

    for i, r in enumerate(results, 1):
        bull  = '多头' if r['bull_ma'] else '    '
        hold  = '[守住]' if r['hold_break'] else '[跌破]'
        fib   = f"{r['retrace_ratio']*100:.0f}%" if r['retrace_ratio'] else '  -'

        if r['hold_break']:
            trail = '未回踩（强势上行）'
        elif r['restable_date']:
            trail = f'回踩{r["pullback_date"][5:]}→企稳{r["restable_date"][5:]}'
        elif r['pullback_date']:
            trail = f'回踩{r["pullback_date"][5:]}→待企稳'
        else:
            trail = '—'

        cvb = r.get('current_vs_break', 0.0)
        cur = r.get('current_close', 0.0)
        dbm = r.get('days_below_ma30', 0)
        cur_str = f'现价{cur:.2f}({cvb:+.1f}%)  跌破MA30后{dbm}天回拉'
        out(f'  {i:>2}  {r["code"]:<10} {r["score"]:>5}  '
            f'{fmt(r["break_date"]):<12} {r["break_close"]:>7.2f} {r["break_pct"]:>+5.1f}%  '
            f'{r["surge_pct"]:>5.0f}%/{r["surge_days"]:>2}天  '
            f'{r["pb_pct"]:>4.0f}%/{r["pullback_days"]:>2}天  '
            f'{fib:>5} {r["shrink_ratio"]:>5.2f}x  '
            f'[{bull}]{hold:<6}  {cur_str}  {trail}')

        # 超大单净流入信息（回调期 + 突破后）
        w_in  = r.get('wash_inflow_days', 0)
        w_tot = r.get('wash_total_days',  0)
        w_net = r.get('wash_net_yi',      0.0)
        a_in  = r.get('after_inflow_days', 0)
        a_tot = r.get('after_total_days',  0)
        a_net = r.get('after_net_yi',      0.0)
        if w_tot > 0 or a_tot > 0:
            w_str = f'净流入{w_in}/{w_tot}天 累计{w_net:+.2f}亿' if w_tot > 0 else '无数据'
            a_str = f'净流入{a_in}/{a_tot}天 累计{a_net:+.2f}亿' if a_tot > 0 else '无数据'
            out(f'      超大单 | 回调期: {w_str}  |  突破后: {a_str}')

    out()
    out('  主升涨=建仓起点到峰值涨幅  回调=从峰值回落幅度  斐波=回调占主升的比例')
    out('  缩量=回调期均量/主升期均量  多头=突破日MA5>MA20>MA60')
    out(f'\n结果已保存：{txt_path}')

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    main()

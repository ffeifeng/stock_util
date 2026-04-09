"""
选股脚本：起爆点分析（供 OpenClaw 调用）
形态：主力建仓 + 缩量洗盘 + 温和突破
用法：python 选股-起爆点分析.py [开始日期] [结束日期]
      日期格式：20260101，不传则用最近5个交易日
输出：D:\soft\选股结果-起爆点.json（供 AI 解析）
"""

import struct
import os
import sys
from datetime import datetime, timedelta

# 让 print 在 Windows 终端也能输出中文（写文件始终用 utf-8）
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


def get_recent_trading_days(n=20):
    """获取最近 n 个交易日的日期范围（简单按自然日近似）
    默认 20 个交易日（约1个月），避免遗漏刚突破但还在强势区的票。
    """
    end = datetime.now()
    start = end - timedelta(days=n + 16)  # 多取些自然日以覆盖节假日
    return int(start.strftime('%Y%m%d')), int(end.strftime('%Y%m%d'))


def read_day_file(filepath):
    records = []
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32:
                    break
                date, open_, high, low, close, amount, volume, reserved = \
                    struct.unpack('<IIIIIfII', chunk)
                records.append({
                    'date': date, 'open': open_ / 100.0, 'high': high / 100.0,
                    'low': low / 100.0, 'close': close / 100.0,
                    'volume': volume, 'amount': amount,
                })
    except Exception:
        pass
    return records


def calc_ma(values, n):
    result = []
    for i in range(len(values)):
        if i < n - 1:
            result.append(None)
        else:
            result.append(sum(values[i - n + 1:i + 1]) / n)
    return result


def find_breakout_day(records, ma30, start_date, end_date):
    """
    找突破 MA30 的日期索引（由下往上穿越），并要求突破后至少连续 2 天收盘仍在 MA30 上方。
    避免把"当天穿越、次日跌回"的假突破当作有效信号。
    """
    for i in range(1, len(records)):
        date = records[i]['date']
        if date < start_date or date > end_date:
            continue
        if ma30[i] is None or ma30[i - 1] is None:
            continue
        if not (records[i - 1]['close'] <= ma30[i - 1] and
                records[i]['close'] > ma30[i]):
            continue
        # 确认：突破日之后至少再有 1 个交易日收盘仍在 MA30 上方（连续 2 天站稳）
        confirmed = False
        for j in range(i + 1, min(i + 4, len(records))):   # 最多看 3 天内是否出现确认日
            if ma30[j] is None:
                continue
            if records[j]['close'] > ma30[j]:
                confirmed = True
                break
        if confirmed:
            return i
    return -1


def detect_pattern_type(records, ma30, bi):
    """
    判断形态类型：
    - 强势型：突破前恰好 1 个交易日跌破 MA30，次日（突破日）立刻拉回上方。
              主力护盘特征明显，仅允许 1 天跌破。
    - 稳健型：突破日之前始终维持 MA30 上方，温和突破。
    - 排除型：突破前连续跌破 MA30 达 2 天及以上，结构偏弱，直接排除。
    - 返回 (type_str, below_days)
    """
    below_days = 0
    for k in range(1, 4):
        idx = bi - k
        if idx < 0:
            break
        if ma30[idx] is None:
            break
        if records[idx]['close'] < ma30[idx]:
            below_days += 1
        else:
            break  # 遇到没跌破的就停，只统计连续跌破天数

    if below_days >= 2:
        return 'excluded', below_days  # 连续跌破 2 天以上，排除
    elif below_days == 1:
        return 'strong', below_days    # 强势型：恰好 1 天跌破，次日立刻拉回
    else:
        return 'stable', 0             # 稳健型：突破前未跌破 MA30


def check_stock(records, break_start, break_end, code=''):
    if len(records) < 200:
        return None

    closes = [r['close'] for r in records]
    volumes = [r['volume'] for r in records]
    ma5  = calc_ma(closes, 5)
    ma20 = calc_ma(closes, 20)
    ma30 = calc_ma(closes, 30)
    ma60 = calc_ma(closes, 60)

    bi = find_breakout_day(records, ma30, break_start, break_end)
    if bi < 60:
        return None

    break_date = records[bi]['date']
    break_close = records[bi]['close']
    break_ma30 = ma30[bi]

    if break_close < 3.0:
        return None

    break_pct = (break_close - break_ma30) / break_ma30 * 100
    if break_pct < 0.5 or break_pct > 12:
        return None

    if ma30[-1] is None:
        return None

    # ── 当前 MA30 状态：允许"刚跌破"（≤2天），但 ≥3天在均线下方视为结构偏弱排除
    current_close = records[-1]['close']
    days_below_now = 0
    for k in range(len(records) - 1, max(len(records) - 10, -1), -1):
        if ma30[k] is None or records[k]['close'] >= ma30[k]:
            break
        days_below_now += 1
    if days_below_now > 2:
        return None

    # 当前价格不能超过突破价 15%（涨多了没必要追）
    current_vs_break = (current_close - break_close) / break_close * 100
    if current_close > break_close * 1.15:
        return None

    wash_end = bi - 1
    wash_start = max(0, bi - 110)  # 洗盘期上限 110 交易日（约5个月）
    wash_records = records[wash_start:wash_end + 1]
    wash_volumes = volumes[wash_start:wash_end + 1]
    wash_closes = closes[wash_start:wash_end + 1]

    if len(wash_records) < 20:     # 最少 20 天（约1个月）
        return None
    if len(wash_records) > 110:    # 最多 110 天（约5个月）
        return None

    below_count = 0
    for j in range(wash_start, wash_end + 1):
        if ma30[j] is None:
            continue
        if records[j]['close'] <= ma30[j] * 1.03:
            below_count += 1
    wash_days = wash_end - wash_start + 1
    if below_count < wash_days * 0.6:
        return None

    pull_end = wash_start
    pull_start = max(0, pull_end - 120)
    pull_records = records[pull_start:pull_end + 1]
    if len(pull_records) < 15:
        return None

    pull_closes = [r['close'] for r in pull_records]
    pull_volumes = [r['volume'] for r in pull_records]
    pull_low = min(pull_closes)
    pull_high = max(pull_closes)
    if pull_low == 0:
        return None

    surge_pct = (pull_high - pull_low) / pull_low * 100
    if surge_pct < 20:
        return None

    # ── 找主力建仓日（洗盘前最大量阳线 = 主力暴力建仓完成日）────────
    # 特征：阳线 + 成交量最大 + 涨幅明显，代表主力集中吸筹的关键日
    yang_pull = [r for r in pull_records if r['close'] > r['open']]
    if not yang_pull:
        return None
    jc_record = max(yang_pull, key=lambda r: r['volume'])

    jc_gain_pct = (jc_record['close'] - jc_record['open']) / jc_record['open'] * 100
    if jc_gain_pct < 2.0:   # 建仓日阳线涨幅不足，非主力积极建仓信号
        return None

    # 建仓日最低价 = 主力建仓成本下沿
    jc_low = jc_record['low']

    avg_vol_pull = sum(pull_volumes) / len(pull_volumes) if pull_volumes else 0
    avg_vol_wash = sum(wash_volumes) / len(wash_volumes) if wash_volumes else 1
    if avg_vol_pull == 0:
        return None

    shrink_ratio = avg_vol_wash / avg_vol_pull
    if shrink_ratio > 0.8:
        return None

    # ── 洗盘深度：不能跌破建仓日最低价的 5% ────────────────────────
    # 真正洗盘是在建仓成本附近震荡；跌幅过深说明主力控盘失败或已出货
    wash_min_close = min(wash_closes)
    if wash_min_close < jc_low * 0.95:
        return None

    # ── MA30 稳定性：洗盘期 MA30 不能持续下行超过 5% ────────────────
    # MA30 下行说明中期趋势向下（出货/下跌），而非真正的横盘洗盘
    if ma30[wash_start] and ma30[wash_end]:
        ma30_drop_pct = (ma30[wash_start] - ma30[wash_end]) / ma30[wash_start] * 100
        if ma30_drop_pct > 8.0:   # MA30 下降超 8% 为出货下跌，而非洗盘
            return None

    # 洗盘振幅：从洗盘期最高点往后计算（消除期间含大涨段的干扰）
    peak_idx_in_wash = max(range(len(wash_closes)), key=lambda k: wash_closes[k])
    post_peak_closes = wash_closes[peak_idx_in_wash:]
    wash_high = max(post_peak_closes)
    wash_low  = min(post_peak_closes)
    if wash_low == 0:
        return None
    wash_range_pct = (wash_high - wash_low) / wash_low * 100
    if wash_range_pct > 35:
        return None

    # ── MA 四线粘合度（洗盘期内 MA5/MA20/MA30/MA60 的平均离散度）────────
    # 每天取四线最大值与最小值之差，除以 MA30 归一化，再取洗盘期平均
    # 值越小表示四线越粘合，说明各周期持仓成本高度集中，弹性越大
    ma_spread_pcts = []
    for j in range(wash_start, wash_end + 1):
        if ma5[j] and ma20[j] and ma30[j] and ma60[j]:
            hi = max(ma5[j], ma20[j], ma30[j], ma60[j])
            lo = min(ma5[j], ma20[j], ma30[j], ma60[j])
            ma_spread_pcts.append((hi - lo) / ma30[j] * 100)
    ma_convergence = round(sum(ma_spread_pcts) / len(ma_spread_pcts), 2) if ma_spread_pcts else 99.0

    vol_ma10 = sum(volumes[bi - 10:bi]) / 10 if bi >= 10 else 0
    break_vol_ratio = volumes[bi] / vol_ma10 if vol_ma10 > 0 else 0
    # 极致粘合形态（ma_convergence < 3%）允许安静突破（量比 >= 0.5x）
    # 普通形态要求量比 >= 0.8x，避免无效假突破
    min_vol_ratio = 0.5 if ma_convergence < 6.0 else 0.8
    if break_vol_ratio < min_vol_ratio or break_vol_ratio > 8:
        return None

    pattern_type, below_days = detect_pattern_type(records, ma30, bi)

    # 连续跌破 MA30 达 2 天以上，结构偏弱，直接排除
    if pattern_type == 'excluded':
        return None

    # 突破后回踩不破突破日收盘价：检查 bi 之后所有交易日收盘均未低于突破日收盘
    # 若从未跌破突破收盘价，说明该价位已成强支撑，主力护盘意志坚定
    hold_breakout_close = all(
        records[j]['close'] >= break_close
        for j in range(bi + 1, len(records))
    )

    # 回踩支撑日：突破后收盘最低的那天
    pullback_date = None
    pullback_close = None
    restable_date = None
    if bi + 1 < len(records):
        post = records[bi + 1:]
        pb_idx = min(range(len(post)), key=lambda i: post[i]['close'])
        pullback_date = post[pb_idx]['date']
        pullback_close = round(post[pb_idx]['close'], 2)

        # 再次企稳日：回踩低点之后第一次收盘重回突破日收盘价以上
        for j in range(bi + 1 + pb_idx + 1, len(records)):
            if records[j]['close'] >= break_close:
                restable_date = records[j]['date']
                break
        # 若回踩低点本身就已 >= 突破收盘（hold_breakout_close），则无需企稳，直接标注
        if hold_breakout_close:
            restable_date = None  # 从未跌破，不存在"再次企稳"

    def fmt_date(d):
        if d is None:
            return None
        s = str(d)
        return f'{s[:4]}-{s[4:6]}-{s[6:]}'

    # ── 超大单净流入统计（ID=11）────────────────────────────────
    cw_data = load_cw_indicator(code, indicator_id=11) if code else {}
    wash_d_start = records[wash_start]['date']
    wash_d_end   = records[wash_end]['date']
    today_d      = records[-1]['date']
    w_in, w_tot, w_net = calc_inflow_stats(cw_data, wash_d_start, wash_d_end)
    a_in, a_tot, a_net = calc_inflow_stats(cw_data, break_date, today_d)

    wash_depth_pct = round((jc_low - wash_min_close) / jc_low * 100, 1)

    return {
        'break_date': break_date,
        'break_close': round(break_close, 2),
        'break_ma30': round(break_ma30, 2),
        'break_pct': round(break_pct, 2),
        'surge_pct': round(surge_pct, 2),
        'shrink_ratio': round(shrink_ratio, 2),
        'wash_range_pct': round(wash_range_pct, 2),
        'wash_days': wash_days,
        'break_vol_ratio': round(break_vol_ratio, 2),
        'ma_convergence': ma_convergence,
        'pattern_type': pattern_type,
        'below_days': below_days,
        'hold_breakout_close': hold_breakout_close,
        'pullback_date': fmt_date(pullback_date),
        'pullback_close': pullback_close,
        'restable_date': fmt_date(restable_date),
        'jc_date': jc_record['date'],
        'jc_low': round(jc_low, 2),
        'wash_min_close': round(wash_min_close, 2),
        'wash_depth_pct': wash_depth_pct,
        'current_close': round(current_close, 2),
        'current_vs_break': round(current_vs_break, 1),
        'days_below_now': days_below_now,
        'wash_inflow_days': w_in,
        'wash_total_days':  w_tot,
        'wash_net_yi':      w_net,
        'after_inflow_days': a_in,
        'after_total_days':  a_tot,
        'after_net_yi':      a_net,
    }


def score(r):
    s = 0
    # ① 建仓涨幅：≤50%最优（说明主力温和建仓，还有主升浪空间），越高越递减
    sp = r['surge_pct']
    if   sp <= 30:   s += 20.0
    elif sp <= 50:   s += 16.0
    elif sp <= 80:   s += 10.0
    elif sp <= 120:  s +=  5.0
    else:            s +=  2.0

    s += (1 - r['shrink_ratio']) * 30

    # ② 洗盘天数：2个月（≈44天）为中心钟形评分，两侧递减，5个月（110天）为上限
    wd = r['wash_days']
    if   38 <= wd <= 50:  s += 20.0   # 2个月附近，最优
    elif 28 <= wd <  38:  s += 14.0   # 1.5个月，偏短侧递减
    elif 50 < wd <=  66:  s += 14.0   # 2~3个月，偏长侧递减
    elif 20 <= wd <  28:  s +=  8.0   # 1个月，再递减
    elif 66 < wd <=  88:  s +=  8.0   # 3~4个月，再递减
    else:                 s +=  3.0   # 88~110天，接近上限，最低分
    s -= r['wash_range_pct'] * 0.2
    s += min(r['break_pct'], 5) * 1.0
    # 强势型加分：跌破MA30后次日立刻拉回，主力护盘特征明显
    if r.get('pattern_type') == 'strong':
        s += 8.0
    # 突破后从未跌破突破收盘价加分：价位已成强支撑，主力高度控盘
    if r.get('hold_breakout_close'):
        s += 10.0
    # MA四线粘合度加分：洗盘期均线离散度越小，弹性越大
    mc = r.get('ma_convergence', 99)
    if   mc < 2.0:  s += 20.0   # 极度粘合（如 002826，弹弓效应最强）
    elif mc < 3.5:  s += 12.0   # 优质粘合
    elif mc < 5.0:  s += 6.0    # 一般粘合
    # 控盘深度加分：洗盘未破建仓日低价说明主力护盘意志强
    wd = r.get('wash_depth_pct', 5.0)
    if   wd <= 0:  s += 15.0   # 洗盘全程高于建仓日低价，控盘极强
    elif wd <= 2:  s += 10.0   # 微幅回落，主力护盘
    elif wd <= 5:  s += 5.0    # 回落在5%内，尚可接受
    return round(s, 1)


def is_valid_stock(code):
    c = code.lower()
    num = c[2:]
    if c.startswith('bj'):
        return False
    if c.startswith('sh'):
        pre3 = num[:3]
        if pre3 in ['600', '601', '602', '603', '604', '605', '688']:
            return True
        return False
    elif c.startswith('sz'):
        pre3 = num[:3]
        if pre3 in ['000', '001', '002', '003', '300', '301']:
            return True
        return False
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


def main():
    # 解析日期参数
    if len(sys.argv) >= 3:
        try:
            break_start = int(sys.argv[1])
            break_end = int(sys.argv[2])
        except ValueError:
            break_start, break_end = get_recent_trading_days()
    else:
        break_start, break_end = get_recent_trading_days()

    st_codes = load_st_codes()
    results = []

    for market, data_dir in DATA_DIRS.items():
        if not os.path.exists(data_dir):
            continue
        files = [f for f in os.listdir(data_dir) if f.endswith('.day')]
        valid_files = []
        for f in files:
            code = f.replace('.day', '')
            if not is_valid_stock(code):
                continue
            num_code = code[2:]
            if num_code in st_codes:
                continue
            valid_files.append(f)
        files = valid_files

        for filename in files:
            code = filename.replace('.day', '')
            filepath = os.path.join(data_dir, filename)
            records = read_day_file(filepath)
            hit = check_stock(records, break_start, break_end, code=code)
            if hit:
                hit['code'] = code
                hit['score'] = score(hit)
                results.append(hit)

    results.sort(key=lambda x: x['score'], reverse=True)

    ts      = datetime.now().strftime('%Y%m%d_%H%M')
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
    os.makedirs(out_dir, exist_ok=True)
    txt_path = os.path.join(out_dir, f'起爆点_{ts}.txt')

    def fmt_date(d):
        s = str(d); return f'{s[:4]}-{s[4:6]}-{s[6:]}'

    lines = []
    def out(s=''):
        lines.append(s)
        print(s)

    out('=' * 80)
    out(f'【起爆点分析】  扫描区间：{break_start} - {break_end}')
    out(f'共找到 {len(results)} 只候选   扫描时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}')
    out('=' * 80)
    out(f'  {"排":>2}  {"代码":<10} {"评分":>5}  {"突破日":<12} {"突破价":>7} {"超MA30":>6}  '
        f'{"洗盘":>4} {"建仓涨":>6} {"缩量":>5}  {"粘合":>5}  {"状态":<7}  {"回踩→企稳"}')
    out('  ' + '─' * 80)

    for i, r in enumerate(results, 1):
        bd    = fmt_date(r['break_date'])
        jcd   = fmt_date(r.get('jc_date', 0)) or '—'
        ptype = '强' if r['pattern_type'] == 'strong' else '稳'
        hold  = '[守住]' if r['hold_breakout_close'] else '[跌破]'
        mc    = r.get('ma_convergence', 99)
        mc_s  = f'{mc:.1f}%{"★" if mc < 2 else ("+" if mc < 3.5 else " ")}'

        if r['hold_breakout_close']:
            trail = '未回踩（强势上行）'
        elif r['restable_date']:
            trail = f'回踩{r["pullback_date"][5:]}→企稳{r["restable_date"][5:]}'
        elif r['pullback_date']:
            trail = f'回踩{r["pullback_date"][5:]}→待企稳'
        else:
            trail = '—'

        cvb = r.get('current_vs_break', 0.0)
        cur = r.get('current_close', 0.0)
        dbn = r.get('days_below_now', 0)
        ma30_state = f'刚破MA30({dbn}天)' if dbn > 0 else '在MA30上方'
        cur_str = f'现价{cur:.2f}({cvb:+.1f}%)  {ma30_state}'
        out(f'  {i:>2}  {r["code"]:<10} {r["score"]:>5}  '
            f'{bd:<12} {r["break_close"]:>7.2f} {r["break_pct"]:>+5.1f}%  '
            f'{r["wash_days"]:>3}天 {r["surge_pct"]:>+5.0f}% {r["shrink_ratio"]:>5.2f}x  '
            f'{mc_s:>6}  [{ptype}]{hold:<6}  {cur_str}  {trail}')
        # 建仓日 + 洗盘深度
        wd = r.get('wash_depth_pct', 0.0)
        if wd <= 0:
            depth_str = f'未破建仓价(高出{abs(wd):.1f}%)'
        else:
            depth_str = f'跌破{wd:.1f}%'
        out(f'      建仓日: {jcd}  建仓低价: {r.get("jc_low","—")}元  '
            f'洗盘最低: {r.get("wash_min_close","—")}元  控盘: {depth_str}')

        # 超大单净流入信息
        w_in  = r.get('wash_inflow_days', 0)
        w_tot = r.get('wash_total_days',  0)
        w_net = r.get('wash_net_yi',      0.0)
        a_in  = r.get('after_inflow_days', 0)
        a_tot = r.get('after_total_days',  0)
        a_net = r.get('after_net_yi',      0.0)
        if w_tot > 0 or a_tot > 0:
            w_str = f'净流入{w_in}/{w_tot}天 累计{w_net:+.2f}亿' if w_tot > 0 else '无数据'
            a_str = f'净流入{a_in}/{a_tot}天 累计{a_net:+.2f}亿' if a_tot > 0 else '无数据'
            out(f'      超大单 | 洗盘: {w_str}  |  突破后: {a_str}')

    out()
    out('  粘合度★<2%极致 +<3.5%优质  缩量=洗盘均量/建仓均量  超MA30=突破日收盘偏离MA30')
    out(f'\n结果已保存：{txt_path}')

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    main()

"""
Binance Day Trading Strategy Analyzer
Fetches live OHLCV data and runs top-tier technical indicators.

Usage:
    python3 analyzer.py                        # default: BTCUSDT 15m
    python3 analyzer.py ETHUSDT 5m
    python3 analyzer.py SOLUSDT 1h
"""

import sys
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime

BINANCE_BASE = "https://api.binance.com"

# ── Data fetch ──────────────────────────────────────────────────────────────

def fetch_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    url = f"{BINANCE_BASE}/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    raw = resp.json()
    df = pd.DataFrame(raw, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    return df.set_index("open_time")


def fetch_ticker(symbol: str) -> dict:
    url = f"{BINANCE_BASE}/api/v3/ticker/24hr"
    resp = requests.get(url, params={"symbol": symbol.upper()}, timeout=10)
    resp.raise_for_status()
    return resp.json()

# ── Indicators ───────────────────────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast=12, slow=26, signal=9):
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(series: pd.Series, period=20, std_dev=2):
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tp_vol = (typical * df["volume"]).cumsum()
    cumulative_vol = df["volume"].cumsum()
    return cumulative_tp_vol / cumulative_vol


def stochastic(df: pd.DataFrame, k_period=14, d_period=3):
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return k, d


def atr(df: pd.DataFrame, period=14) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()

# ── Signal engine ─────────────────────────────────────────────────────────────

def score_signal(label: str, condition: bool, bull_points: int, bear_points: int,
                 bull_score: list, bear_score: list, notes: list):
    if condition:
        bull_score.append(bull_points)
        notes.append(f"  [+{bull_points} BULL] {label}")
    else:
        bear_score.append(bear_points)
        notes.append(f"  [-{bear_points} BEAR] {label}")


def analyze(symbol: str, interval: str):
    print(f"\n{'='*60}")
    print(f"  BINANCE ANALYZER  |  {symbol.upper()}  |  {interval}")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*60}")

    df = fetch_klines(symbol, interval, limit=200)
    ticker = fetch_ticker(symbol)

    close = df["close"]
    current_price = close.iloc[-1]
    prev_close = close.iloc[-2]

    # ── Compute indicators ──
    ema9 = ema(close, 9)
    ema21 = ema(close, 21)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)

    rsi14 = rsi(close, 14)
    macd_line, macd_signal, macd_hist = macd(close)

    bb_upper, bb_mid, bb_lower = bollinger_bands(close, 20, 2)
    bb_width = (bb_upper - bb_lower) / bb_mid * 100

    vwap_line = vwap(df)
    stoch_k, stoch_d = stochastic(df)
    atr14 = atr(df, 14)

    # Last values
    r = rsi14.iloc[-1]
    r_prev = rsi14.iloc[-2]
    mk = macd_line.iloc[-1]
    ms = macd_signal.iloc[-1]
    mh = macd_hist.iloc[-1]
    mh_prev = macd_hist.iloc[-2]
    sk = stoch_k.iloc[-1]
    sd = stoch_d.iloc[-1]
    atr_val = atr14.iloc[-1]
    bb_pct = (current_price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]) * 100

    bull_score, bear_score, notes = [], [], []

    # ── Strategy signals ──
    score_signal(
        f"EMA Trend: 9({ema9.iloc[-1]:.4f}) vs 21({ema21.iloc[-1]:.4f})",
        ema9.iloc[-1] > ema21.iloc[-1], 2, 2, bull_score, bear_score, notes
    )
    score_signal(
        f"EMA Stack: price({current_price:.4f}) > EMA50({ema50.iloc[-1]:.4f})",
        current_price > ema50.iloc[-1], 2, 2, bull_score, bear_score, notes
    )
    score_signal(
        f"EMA200 Filter: price({current_price:.4f}) > EMA200({ema200.iloc[-1]:.4f})",
        current_price > ema200.iloc[-1], 1, 1, bull_score, bear_score, notes
    )
    score_signal(
        f"RSI({r:.1f}): momentum {'rising' if r > r_prev else 'falling'}, range 30-70",
        30 < r < 70 and r > r_prev, 2, 1, bull_score, bear_score, notes
    )
    score_signal(
        f"MACD: histogram {'expanding' if abs(mh) > abs(mh_prev) else 'contracting'} ({mh:.6f})",
        mk > ms and mh > mh_prev, 2, 2, bull_score, bear_score, notes
    )
    score_signal(
        f"VWAP: price({current_price:.4f}) vs VWAP({vwap_line.iloc[-1]:.4f})",
        current_price > vwap_line.iloc[-1], 2, 2, bull_score, bear_score, notes
    )
    score_signal(
        f"Stochastic K({sk:.1f}) D({sd:.1f}): K > D and not overbought",
        sk > sd and sk < 80, 1, 1, bull_score, bear_score, notes
    )
    score_signal(
        f"Bollinger %B({bb_pct:.1f}%): in mid zone (20%-80%)",
        20 < bb_pct < 80, 1, 1, bull_score, bear_score, notes
    )

    total_bull = sum(bull_score)
    total_bear = sum(bear_score)
    total = total_bull + total_bear
    bull_pct = total_bull / total * 100 if total > 0 else 50

    # Determine signal
    if bull_pct >= 70:
        signal = "LONG  (Strong Buy)"
        signal_char = "▲"
    elif bull_pct >= 55:
        signal = "LONG  (Weak Buy)"
        signal_char = "△"
    elif bull_pct <= 30:
        signal = "SHORT (Strong Sell)"
        signal_char = "▼"
    elif bull_pct <= 45:
        signal = "SHORT (Weak Sell)"
        signal_char = "▽"
    else:
        signal = "NEUTRAL (Wait)"
        signal_char = "◇"

    # RSI zone label
    if r >= 70:
        rsi_zone = "OVERBOUGHT"
    elif r <= 30:
        rsi_zone = "OVERSOLD"
    elif r >= 55:
        rsi_zone = "Bullish"
    elif r <= 45:
        rsi_zone = "Bearish"
    else:
        rsi_zone = "Neutral"

    # ── Print summary ──
    print(f"\n  Price:      ${current_price:,.4f}  ({float(ticker['priceChangePercent']):+.2f}% 24h)")
    print(f"  24h Vol:    {float(ticker['volume']):,.0f} {symbol[:3]}")
    print(f"  ATR(14):    {atr_val:.4f}  ({atr_val/current_price*100:.2f}% of price)")
    print(f"  BB Width:   {bb_width.iloc[-1]:.2f}%")
    print(f"  RSI(14):    {r:.1f}  [{rsi_zone}]")
    print(f"  MACD hist:  {mh:+.6f}  ({'expanding' if abs(mh) > abs(mh_prev) else 'contracting'})")
    print(f"  Stoch K/D:  {sk:.1f} / {sd:.1f}")
    print(f"  VWAP:       {vwap_line.iloc[-1]:.4f}")

    print(f"\n  Signal breakdown:")
    for note in notes:
        print(note)

    print(f"\n  Score:  BULL {total_bull}pt  |  BEAR {total_bear}pt  |  Bull% {bull_pct:.0f}%")
    print(f"\n  {signal_char}  SIGNAL: {signal}")

    # ── Risk levels ──
    if "LONG" in signal:
        entry = current_price
        stop = round(current_price - atr_val * 1.5, 4)
        tp1 = round(current_price + atr_val * 2, 4)
        tp2 = round(current_price + atr_val * 3.5, 4)
        print(f"\n  Suggested levels (1.5x ATR stop, 2x/3.5x ATR targets):")
        print(f"    Entry:  ${entry:,.4f}")
        print(f"    Stop:   ${stop:,.4f}  (-{(entry-stop)/entry*100:.2f}%)")
        print(f"    TP1:    ${tp1:,.4f}  (+{(tp1-entry)/entry*100:.2f}%)")
        print(f"    TP2:    ${tp2:,.4f}  (+{(tp2-entry)/entry*100:.2f}%)")
    elif "SHORT" in signal:
        entry = current_price
        stop = round(current_price + atr_val * 1.5, 4)
        tp1 = round(current_price - atr_val * 2, 4)
        tp2 = round(current_price - atr_val * 3.5, 4)
        print(f"\n  Suggested levels (1.5x ATR stop, 2x/3.5x ATR targets):")
        print(f"    Entry:  ${entry:,.4f}")
        print(f"    Stop:   ${stop:,.4f}  (+{(stop-entry)/entry*100:.2f}%)")
        print(f"    TP1:    ${tp1:,.4f}  (-{(entry-tp1)/entry*100:.2f}%)")
        print(f"    TP2:    ${tp2:,.4f}  (-{(entry-tp2)/entry*100:.2f}%)")
    else:
        print(f"\n  No trade — wait for a clearer setup.")

    print(f"\n{'='*60}")
    print("  DISCLAIMER: For educational use only. Not financial advice.")
    print(f"{'='*60}\n")


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    interval = sys.argv[2] if len(sys.argv) > 2 else "15m"

    valid_intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
    if interval not in valid_intervals:
        print(f"Invalid interval '{interval}'. Choose from: {', '.join(valid_intervals)}")
        sys.exit(1)

    try:
        analyze(symbol, interval)
    except requests.exceptions.HTTPError as e:
        print(f"\nAPI error: {e}")
        print("Check that the symbol is valid (e.g. BTCUSDT, ETHUSDT, SOLUSDT)")
    except Exception as e:
        print(f"\nError: {e}")

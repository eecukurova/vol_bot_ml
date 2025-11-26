#!/usr/bin/env python3
"""
ORB Breakout optimizer tuned for volatile meme/perp coins (e.g. PENGUSDT.P).

Compared to the AVAX scripts this version:
  * pulls data from any CCXT-supported exchange (default BingX swap)
  * normalises TradingView-style tickers such as PENGUSDT.P -> PENG/USDT:USDT
  * exposes CLI arguments for symbol, timeframe, lookback window and exchange
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Dict, Any, List

import ccxt  # type: ignore
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.strategy.orb_breakout import ORBBreakoutStrategy  # noqa: E402


def _convert_symbol(raw_symbol: str, market_type: str) -> str:
    """
    Convert TradingView style tickers (e.g. PENGUSDT.P) to CCXT format.
    """
    if "/" in raw_symbol:
        return raw_symbol

    symbol = raw_symbol.upper()
    if symbol.endswith(".P"):
        symbol = symbol[:-2]

    for quote in ("USDT", "USDC", "USD", "FDUSD"):
        if symbol.endswith(quote):
            base = symbol[: -len(quote)]
            if not base:
                break
            if market_type.lower() in {"swap", "future", "perpetual"}:
                return f"{base}/{quote}:USDT"
            return f"{base}/{quote}"

    return raw_symbol


def _init_exchange(exchange_name: str, market_type: str):
    exchange_name = exchange_name.lower()
    if not hasattr(ccxt, exchange_name):
        raise ValueError(f"Unsupported exchange '{exchange_name}'")

    exchange_class = getattr(ccxt, exchange_name)
    market_type = market_type.lower()

    opts: Dict[str, Any] = {"enableRateLimit": True, "options": {}}
    opts["options"]["defaultType"] = "swap" if market_type in {"swap", "future", "perpetual"} else market_type
    if market_type in {"swap", "future", "perpetual"}:
        opts["options"].update(
            {
                "defaultContractType": "swap",
                "defaultMarket": "swap",
            }
        )

    exchange = exchange_class(opts)
    exchange.load_markets()
    return exchange


def download_ccxt_klines(
    exchange_name: str,
    symbol: str,
    timeframe: str,
    days: int,
    market_type: str = "swap",
    max_candles: int = 12_000,
) -> pd.DataFrame:
    """
    Fetch historical candles with automatic pagination.
    """
    exchange = _init_exchange(exchange_name, market_type)
    ccxt_symbol = _convert_symbol(symbol, market_type)

    if ccxt_symbol not in exchange.symbols:
        upper_symbols = {s.upper(): s for s in exchange.symbols}
        if ccxt_symbol.upper() in upper_symbols:
            ccxt_symbol = upper_symbols[ccxt_symbol.upper()]
        elif ":" in ccxt_symbol:
            spot_symbol = ccxt_symbol.split(":")[0]
            # re-init exchange for spot data
            spot_exchange = _init_exchange(exchange_name, "spot")
            upper_spot_symbols = {s.upper(): s for s in spot_exchange.symbols}
            if spot_symbol in spot_exchange.symbols:
                print(f"⚠️  Falling back to spot market {spot_symbol} (derivative not available)")
                exchange = spot_exchange
                ccxt_symbol = spot_symbol
            elif spot_symbol.upper() in upper_spot_symbols:
                ccxt_symbol = upper_spot_symbols[spot_symbol.upper()]
                exchange = spot_exchange
                print(f"⚠️  Falling back to spot market {ccxt_symbol} (derivative not available)")
            else:
                raise ValueError(
                    f"Symbol '{symbol}' not found on {exchange_name} (tried swap + spot)."
                )
        else:
            raise ValueError(
                f"Symbol '{symbol}' not found on {exchange_name}. "
                f"Available example: {next(iter(exchange.symbols), 'N/A')}"
            )

    timeframe_ms = int(exchange.parse_timeframe(timeframe) * 1000)
    since = exchange.milliseconds() - days * 24 * 60 * 60 * 1000
    now = exchange.milliseconds()

    all_ohlcv: List[List[float]] = []
    limit = getattr(exchange, "max_fetch_ohlcv_limit", None) or 1000
    while since < now and len(all_ohlcv) < max_candles:
        batch = exchange.fetch_ohlcv(ccxt_symbol, timeframe, since=since, limit=limit)
        if not batch:
            break
        all_ohlcv.extend(batch)
        since = batch[-1][0] + timeframe_ms
        # rate limit safety
        time.sleep((exchange.rateLimit or 1200) / 1000)

    if not all_ohlcv:
        raise RuntimeError(f"No OHLCV data downloaded for {ccxt_symbol} on {exchange_name}")

    df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df.sort_index().drop_duplicates()
    df = df.tz_localize(None)
    return df


def score_result(results: Dict[str, Any]) -> float:
    """
    Scoring heuristic emphasising profit factor + drawdown + win rate.
    """
    capped_return = min(results["total_return_pct"], 20_000)
    score = (
        results["profit_factor"] * 25
        + results["win_rate"] * 1.2
        + capped_return * 0.12
        - results["max_drawdown_pct"] * 1.1
    )
    if results["total_trades"] < 5:
        score -= 10
    return score


def optimize_orb_for_symbol(
    symbol: str,
    timeframe: str,
    exchange: str,
    market_type: str,
    days: int,
) -> Dict[str, Any]:
    print(f"\n{'=' * 80}")
    print(f"🚀 ORB Breakout Optimizer for {symbol} ({exchange}, {timeframe})")
    print(f"{'=' * 80}\n")

    print(f"📥 Downloading {symbol} data from {exchange} ({timeframe}, {days}d)...")
    df = download_ccxt_klines(exchange, symbol, timeframe, days, market_type)
    print(f"✅ Downloaded {len(df)} candles from {df.index[0]} to {df.index[-1]}")

    # Parametre ızgarası: daha geniş / agresif aralıklar
    orb_minutes = [5, 15, 30]
    breakout_buffer_pcts = [0.15, 0.25, 0.35]
    min_bars_outside = [1, 2, 3]

    enable_volume_filter = [False, True]
    volume_multipliers = [1.2, 1.5, 2.0]

    enable_trend_filter = [False, True]
    trend_modes = ["VWAP", "EMA", "VWAP+EMA"]

    tp1_pcts = [0.9, 1.4, 2.0]
    tp2_pcts = [2.0, 2.8, 4.0]
    tp3_pcts = [3.2, 4.5, 6.0, 8.0]
    stop_modes = ["Smart Adaptive", "% Based"]
    atr_multipliers = [0.8, 1.2, 1.6, 2.0]

    param_space = list(
        product(
            orb_minutes,
            breakout_buffer_pcts,
            min_bars_outside,
            enable_volume_filter,
            volume_multipliers,
            enable_trend_filter,
            trend_modes,
            tp1_pcts,
            tp2_pcts,
            tp3_pcts,
            stop_modes,
            atr_multipliers,
        )
    )

    print(f"\n📊 Testing {len(param_space):,} parameter combinations...")
    best_result = None
    best_score = -float("inf")
    all_results: List[Dict[str, Any]] = []
    start = time.time()

    for idx, combo in enumerate(param_space, 1):
        (
            orb_min,
            buf_pct,
            min_bars,
            vol_filter,
            vol_mult,
            trend_filter,
            trend_mode,
            tp1,
            tp2,
            tp3,
            stop_mode,
            atr_mult,
        ) = combo

        params = {
            "orb_minutes": orb_min,
            "breakout_buffer_pct": buf_pct,
            "min_bars_outside": min_bars,
            "enable_volume_filter": vol_filter,
            "volume_ma_length": 20,
            "volume_multiplier": vol_mult,
            "enable_trend_filter": trend_filter,
            "trend_mode": trend_mode,
            "trend_ema_length": 21,
            "tp1_pct": tp1,
            "tp2_pct": tp2,
            "tp3_pct": tp3,
            "stop_mode": stop_mode,
            "atr_length": 14,
            "atr_multiplier": atr_mult,
            "max_stop_loss_pct": 1.5,
            "leverage": 5.0,
            "commission": 0.0005,
            "slippage": 0.0003,
        }

        try:
            strategy = ORBBreakoutStrategy(params)
            result = strategy.run_backtest(df)
        except Exception:
            continue

        if result["total_trades"] < 3 or result["total_trades"] > 600:
            continue

        score = score_result(result)
        entry = {"params": params, "results": result, "score": score}
        all_results.append(entry)

        if score > best_score:
            best_score = score
            best_result = entry
            print(
                f"\n⭐ New best (#{idx}/{len(param_space)}): "
                f"Score {score:.1f} | Trades {result['total_trades']} | "
                f"WR {result['win_rate']:.1f}% | PF {result['profit_factor']:.2f} | "
                f"Return {result['total_return_pct']:.1f}%"
            )

        if idx % 150 == 0:
            elapsed = time.time() - start
            pct = idx / len(param_space) * 100
            print(f"Progress {pct:.1f}% | Tested {idx} combos | Best {best_score:.1f} | {elapsed/60:.1f}m elapsed")

    if not all_results:
        raise RuntimeError("No valid optimization results generated.")

    all_results.sort(key=lambda x: x["score"], reverse=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = ROOT / f"orb_peng_optimization_{timestamp}.json"
    with open(output_file, "w") as fh:
        json.dump(
            [
                {
                    "score": r["score"],
                    "params": r["params"],
                    "results": {k: v for k, v in r["results"].items() if k != "trades"},
                }
                for r in all_results[:50]
            ],
            fh,
            indent=2,
        )

    print(f"\n✅ Optimization complete — saved top results to {output_file}")
    return {"best": best_result, "all": all_results[:10]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimize ORB strategy for meme/perp coins.")
    parser.add_argument("--symbol", default="PENGUSDT.P", help="Trading symbol (TradingView or CCXT style)")
    parser.add_argument("--timeframe", default="15m", help="Timeframe to backtest (default: 15m)")
    parser.add_argument("--days", type=int, default=120, help="History window in days")
    parser.add_argument("--exchange", default="gate", help="CCXT exchange name (default: gate.io)")
    parser.add_argument("--market-type", default="swap", help="Market type: spot | swap | future")
    return parser.parse_args()


def main():
    args = parse_args()
    results = optimize_orb_for_symbol(
        symbol=args.symbol,
        timeframe=args.timeframe,
        exchange=args.exchange,
        market_type=args.market_type,
        days=args.days,
    )

    best = results["best"]
    if best:
        r = best["results"]
        p = best["params"]
        print("\n🏆 Best configuration summary")
        print(f"Trades: {r['total_trades']} | WinRate: {r['win_rate']:.2f}% | PF: {r['profit_factor']:.2f}")
        print(f"Return: {r['total_return_pct']:.2f}% | MaxDD: {r['max_drawdown_pct']:.2f}%")
        print(
            f"ORB {p['orb_minutes']}m | Buffer {p['breakout_buffer_pct']}% | "
            f"Volume Filter {p['enable_volume_filter']} (x{p['volume_multiplier']})"
        )
        print(
            f"Trend Filter {p['enable_trend_filter']} ({p['trend_mode']}) | "
            f"TPs {p['tp1_pct']}/{p['tp2_pct']}/{p['tp3_pct']}% | Stop {p['stop_mode']} ×{p['atr_multiplier']}"
        )


if __name__ == "__main__":
    main()


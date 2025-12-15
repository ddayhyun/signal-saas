# apps/engine/run_local.py
from .datafeed import fetch_ohlcv_binance
from .strategy_v1 import apply_indicators
from .simulator import simulate_spot, SimConfig

def main():
    df = fetch_ohlcv_binance(symbol="BTC/USDT", timeframe="1h", limit=1500)
    df = apply_indicators(df, fast=20, slow=50, rsi_period=14)

    result = simulate_spot(df, SimConfig(fee_roundtrip=0.002, stop_loss=0.02, take_profit=0.04))
    trades = result["trades"]
    equity = result["equity"]

    print(f"Trades: {len(trades)}")
    if len(trades) > 0:
        winrate = (trades["return"] > 0).mean()
        total_return = equity.iloc[-1] - 1.0
        print(f"WinRate: {winrate:.3f}")
        print(f"TotalReturn (sim): {total_return:.3f}")
        print(trades.tail(5).to_string(index=False))
    else:
        print("No trades generated. (Try adjusting parameters or window length.)")

if __name__ == "__main__":
    main()

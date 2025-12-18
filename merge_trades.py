"""
Merge WBTC/USDT and WBTC/USDC trades into a single BTC-USD CSV file.

Usage: uv run merge_trades.py
"""

import csv
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

START_DATE = None  # e.g., "2024-01-01" or None for all
END_DATE = None  # e.g., "2024-12-31" or None for latest
MIN_VOLUME_USD = 100  # Minimum trade volume in USD

# =============================================================================


def parse_date(date_str):
    if date_str is None:
        return None
    return datetime.fromisoformat(date_str)


def load_trades(filepath, stablecoin):
    trades = []
    with open(filepath) as f:
        for row in csv.DictReader(f):
            ts = datetime.fromisoformat(row["timestamp"])
            stab = stablecoin.lower()

            wbtc_usd = float(row["wbtc_amount_usd"])
            stablecoin_usd = float(row[f"{stab}_amount_usd"])
            total_usd_volume = (wbtc_usd + stablecoin_usd) / 2

            direction = row["direction"]
            if direction.startswith("WBTC_TO_"):
                normalized = "SELL"  # selling WBTC for stablecoin
            else:
                normalized = "BUY"  # buying WBTC with stablecoin

            trades.append(
                {
                    "unix_timestamp": int(ts.timestamp()),
                    "datetime": ts,
                    "date": ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "direction": normalized,
                    "wbtc_amount": float(row["wbtc_amount"]),
                    "usd_amount": float(row[f"{stab}_amount"]),
                    "price": float(row[f"effective_price_{stab}_per_wbtc"]),
                    "total_usd_volume": total_usd_volume,
                    "source": stablecoin,
                }
            )
    return trades


def filter_trades(trades, start_date, end_date, min_volume):
    filtered = []
    for t in trades:
        if start_date and t["datetime"].date() < start_date.date():
            continue
        if end_date and t["datetime"].date() > end_date.date():
            continue
        if t["total_usd_volume"] < min_volume:
            continue
        filtered.append(t)
    return filtered


def write_csv(trades, output_path):
    trades.sort(key=lambda t: t["unix_timestamp"], reverse=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "unix_timestamp",
                "date",
                "direction",
                "wbtc_amount",
                "usd_amount",
                "price",
                "total_usd_volume",
                "source",
            ]
        )
        for t in trades:
            writer.writerow(
                [
                    t["unix_timestamp"],
                    t["date"],
                    t["direction"],
                    f"{t['wbtc_amount']:.8f}",
                    f"{t['usd_amount']:.2f}",
                    f"{t['price']:.2f}",
                    f"{t['total_usd_volume']:.2f}",
                    t["source"],
                ]
            )


# Main
start = parse_date(START_DATE)
end = parse_date(END_DATE)

print("Merging WBTC/USDT and WBTC/USDC trades")
print(
    f"Start: {start.date() if start else 'All'} | End: {end.date() if end else 'Latest'} | Min volume: ${MIN_VOLUME_USD}"
)
print()

all_trades = []

for stablecoin, filename in [
    ("USDT", "wbtc_usdt_trades.csv"),
    ("USDC", "wbtc_usdc_trades.csv"),
]:
    path = Path(filename)
    if path.exists():
        trades = load_trades(path, stablecoin)
        print(f"Loaded {len(trades)} {stablecoin} trades")
        all_trades.extend(trades)

print(f"Total: {len(all_trades)} trades")

filtered = filter_trades(all_trades, start, end, MIN_VOLUME_USD)
print(f"After filtering: {len(filtered)} trades")

if filtered:
    oldest = min(t["datetime"] for t in filtered)
    newest = max(t["datetime"] for t in filtered)
    total_wbtc = sum(t["wbtc_amount"] for t in filtered)
    total_usd = sum(t["usd_amount"] for t in filtered)
    buys = sum(1 for t in filtered if t["direction"] == "BUY")
    sells = len(filtered) - buys

    print(f"Date range: {oldest.date()} to {newest.date()}")
    print(f"BUY: {buys} | SELL: {sells}")
    print(f"Volume: {total_wbtc:.2f} WBTC / ${total_usd:,.0f}")

write_csv(filtered, "btcusd-cowswap.csv")
print("Written to btcusd-cowswap.csv")

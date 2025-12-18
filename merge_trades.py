"""
Merge USDT and USDC trades for a given crypto asset into a single USD CSV file.

Usage: uv run merge_trades.py
"""

import csv
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

CRYPTO = "WBTC"  # "WBTC" or "WETH"
START_DATE = None  # e.g., "2024-01-01" or None for all
END_DATE = None  # e.g., "2024-12-31" or None for latest
MIN_VOLUME_USD = 100  # Minimum trade volume in USD

# =============================================================================

# Mapping from crypto to output filename and column names
CRYPTO_CONFIG = {
    "WBTC": {
        "output_file": "btcusd-cowswap.csv",
        "amount_col": "wbtc_amount",
        "usd_col_template": "{stab}_amount",
        "price_col_template": "effective_price_{stab}_per_wbtc",
        "usd_amount_col": "wbtc_amount_usd",
    },
    "WETH": {
        "output_file": "ethusd-cowswap.csv",
        "amount_col": "weth_amount",
        "usd_col_template": "{stab}_amount",
        "price_col_template": "effective_price_{stab}_per_weth",
        "usd_amount_col": "weth_amount_usd",
    },
}


def parse_date(date_str):
    if date_str is None:
        return None
    return datetime.fromisoformat(date_str)


def load_trades(filepath, stablecoin, crypto):
    config = CRYPTO_CONFIG[crypto]
    trades = []
    with open(filepath) as f:
        for row in csv.DictReader(f):
            ts = datetime.fromisoformat(row["timestamp"])
            stab = stablecoin.lower()

            crypto_usd = float(row[config["usd_amount_col"]])
            stablecoin_usd = float(row[f"{stab}_amount_usd"])
            total_usd_volume = (crypto_usd + stablecoin_usd) / 2

            direction = row["direction"]
            if direction.startswith(f"{crypto}_TO_"):
                normalized = "SELL"  # selling crypto for stablecoin
            else:
                normalized = "BUY"  # buying crypto with stablecoin

            amount_col = config["amount_col"]
            price_col = config["price_col_template"].format(stab=stab)

            trades.append(
                {
                    "unix_timestamp": int(ts.timestamp()),
                    "datetime": ts,
                    "date": ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "direction": normalized,
                    "crypto_amount": float(row[amount_col]),
                    "usd_amount": float(row[f"{stab}_amount"]),
                    "price": float(row[price_col]),
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


def write_csv(trades, output_path, crypto):
    trades.sort(key=lambda t: t["unix_timestamp"], reverse=True)

    # Use lowercase crypto name for column header
    amount_header = f"{crypto.lower()}_amount"

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "unix_timestamp",
                "date",
                "direction",
                amount_header,
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
                    f"{t['crypto_amount']:.8f}",
                    f"{t['usd_amount']:.2f}",
                    f"{t['price']:.2f}",
                    f"{t['total_usd_volume']:.2f}",
                    t["source"],
                ]
            )


# Main
config = CRYPTO_CONFIG[CRYPTO]
start = parse_date(START_DATE)
end = parse_date(END_DATE)

print(f"Merging {CRYPTO}/USDT and {CRYPTO}/USDC trades")
print(
    f"Start: {start.date() if start else 'All'} | End: {end.date() if end else 'Latest'} | Min volume: ${MIN_VOLUME_USD}"
)
print()

all_trades = []

for stablecoin in ["USDT", "USDC"]:
    filename = f"{CRYPTO.lower()}_{stablecoin.lower()}_trades.csv"
    path = Path(filename)
    if path.exists():
        trades = load_trades(path, stablecoin, CRYPTO)
        print(f"Loaded {len(trades)} {stablecoin} trades")
        all_trades.extend(trades)
    else:
        print(f"File not found: {filename}")

print(f"Total: {len(all_trades)} trades")

filtered = filter_trades(all_trades, start, end, MIN_VOLUME_USD)
print(f"After filtering: {len(filtered)} trades")

if filtered:
    oldest = min(t["datetime"] for t in filtered)
    newest = max(t["datetime"] for t in filtered)
    total_crypto = sum(t["crypto_amount"] for t in filtered)
    total_usd = sum(t["usd_amount"] for t in filtered)
    buys = sum(1 for t in filtered if t["direction"] == "BUY")
    sells = len(filtered) - buys

    print(f"Date range: {oldest.date()} to {newest.date()}")
    print(f"BUY: {buys} | SELL: {sells}")
    print(f"Volume: {total_crypto:.2f} {CRYPTO} / ${total_usd:,.0f}")

output_file = config["output_file"]
write_csv(filtered, output_file, CRYPTO)
print(f"Written to {output_file}")

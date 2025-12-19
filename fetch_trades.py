"""
Fetch historical trades from CoW Protocol subgraph.

Edit the configuration section below to choose which token pairs to fetch.

Outputs one CSV per pair to `data/partial/`.
"""

import csv
import json
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import httpx
from dotenv import load_dotenv

# =============================================================================
# CONFIGURATION
# =============================================================================

# TOKENS_A = ["wbtc", "cbbtc"]  # e.g. ["eth"], ["wbtc", "cbbtc"], ["weth"]
TOKENS_A = ["eth", "weth"]
TOKENS_B = ["usdc", "usdt"]  # quote tokens (stablecoins)

PAGE_SIZE = 1000

SUBGRAPH_ID = "8mdwJG7YCSwqfxUbhCypZvoubeZcFVpCHb4zmHhvuKTD"

DATA_DIR = Path(__file__).resolve().parent / "data"
PARTIAL_DIR = DATA_DIR / "partial"
TOKEN_ADDRESSES_PATH = Path(__file__).resolve().parent / "token-addresses.json"

# =============================================================================

load_dotenv()


def load_token_map(filepath):
    with open(filepath) as f:
        raw = json.load(f)

    token_map = {}
    for name, info in raw.items():
        if not isinstance(info, dict):
            continue
        token_map[name.lower()] = {
            "address": (info.get("address") or "").lower(),
            "decimals": int(info.get("decimals")),
        }
    return token_map


def get_token_info(token_map, token_name):
    token = token_name.lower()
    if token not in token_map:
        raise KeyError(f"Token '{token_name}' missing from {TOKEN_ADDRESSES_PATH.name}")

    info = token_map[token]
    if not info.get("address"):
        raise ValueError(
            f"Token '{token_name}' has an empty address in {TOKEN_ADDRESSES_PATH.name}"
        )
    return info


def query_subgraph(subgraph_url, query):
    response = httpx.post(
        subgraph_url,
        json={"query": query},
        headers={
            "Content-Type": "application/json",
            "User-Agent": "cowswap-auctions/1.0",
        },
        timeout=60.0,
    )
    response.raise_for_status()
    result = response.json()
    if "errors" in result:
        raise Exception(f"GraphQL errors: {result['errors']}")
    return result


def fetch_trades_page(
    subgraph_url, sell_token, buy_token, last_timestamp=None, last_id=None
):
    where = f'sellToken_: {{address: "{sell_token}"}}, buyToken_: {{address: "{buy_token}"}}'
    if last_timestamp is not None and last_id is not None:
        where = f'{where}, timestamp_lte: {last_timestamp}, id_not: "{last_id}"'

    query = f"""
    {{ trades(first: {PAGE_SIZE}, orderBy: timestamp, orderDirection: desc, where: {{{where}}}) {{
        id timestamp sellAmount buyAmount sellAmountUsd buyAmountUsd txHash
    }} }}
    """
    return query_subgraph(subgraph_url, query).get("data", {}).get("trades", [])


def fetch_all_trades(subgraph_url, token_map, base, quote, direction):
    base_info = get_token_info(token_map, base)
    quote_info = get_token_info(token_map, quote)

    trades_out = []
    last_timestamp, last_id = None, None
    page = 0

    is_base_sell = direction.startswith(f"{base.upper()}_TO_")
    sell_addr = base_info["address"] if is_base_sell else quote_info["address"]
    buy_addr = quote_info["address"] if is_base_sell else base_info["address"]

    while True:
        page += 1
        print(f"  Page {page} ({direction})...", end=" ", flush=True)
        trades = fetch_trades_page(
            subgraph_url, sell_addr, buy_addr, last_timestamp, last_id
        )

        if not trades:
            print("done")
            break
        print(f"{len(trades)} trades")

        for t in trades:
            ts = datetime.fromtimestamp(int(t["timestamp"]))
            sell_amt = Decimal(t["sellAmount"])
            buy_amt = Decimal(t["buyAmount"])
            sell_usd = Decimal(t["sellAmountUsd"] or 0)
            buy_usd = Decimal(t["buyAmountUsd"] or 0)

            if is_base_sell:
                base_raw, quote_raw, base_usd, quote_usd = (
                    sell_amt,
                    buy_amt,
                    sell_usd,
                    buy_usd,
                )
            else:
                base_raw, quote_raw, base_usd, quote_usd = (
                    buy_amt,
                    sell_amt,
                    buy_usd,
                    sell_usd,
                )

            base_amount = base_raw / Decimal(10 ** base_info["decimals"])
            quote_amount = quote_raw / Decimal(10 ** quote_info["decimals"])
            price = quote_amount / base_amount if base_amount > 0 else Decimal(0)

            trades_out.append(
                {
                    "id": t["id"],
                    "timestamp": ts,
                    "direction": direction,
                    "base_amount": base_amount,
                    "quote_amount": quote_amount,
                    "base_amount_usd": base_usd,
                    "quote_amount_usd": quote_usd,
                    "effective_price": price,
                    "tx_hash": t["txHash"],
                }
            )

        last_timestamp, last_id = int(trades[-1]["timestamp"]), trades[-1]["id"]
        if len(trades) < PAGE_SIZE:
            break

    return trades_out


def fetch_pair(subgraph_url, token_map, base, quote):
    print(f"Fetching {base} -> {quote}...")
    fwd = fetch_all_trades(
        subgraph_url,
        token_map,
        base,
        quote,
        f"{base.upper()}_TO_{quote.upper()}",
    )
    print(f"  Total: {len(fwd)}")

    print(f"Fetching {quote} -> {base}...")
    rev = fetch_all_trades(
        subgraph_url,
        token_map,
        base,
        quote,
        f"{quote.upper()}_TO_{base.upper()}",
    )
    print(f"  Total: {len(rev)}")

    all_trades = fwd + rev
    all_trades.sort(key=lambda t: t["timestamp"], reverse=True)
    return all_trades


def export_csv(trades, filepath, base, quote):
    b, q = base.lower(), quote.lower()
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp",
                "direction",
                f"{b}_amount",
                f"{q}_amount",
                f"effective_price_{q}_per_{b}",
                f"{b}_amount_usd",
                f"{q}_amount_usd",
                "tx_hash",
                "trade_id",
            ]
        )
        for t in trades:
            writer.writerow(
                [
                    t["timestamp"].isoformat(),
                    t["direction"],
                    f"{t['base_amount']:.8f}",
                    f"{t['quote_amount']:.6f}",
                    f"{t['effective_price']:.2f}",
                    f"{t['base_amount_usd']:.2f}",
                    f"{t['quote_amount_usd']:.2f}",
                    t["tx_hash"],
                    t["id"],
                ]
            )


def main():
    graph_api_key = os.getenv("GRAPH_API_KEY")
    if not graph_api_key:
        raise SystemExit("Missing GRAPH_API_KEY (set it in .env)")

    subgraph_url = (
        f"https://gateway.thegraph.com/api/{graph_api_key}/subgraphs/id/{SUBGRAPH_ID}"
    )

    token_map = load_token_map(TOKEN_ADDRESSES_PATH)

    PARTIAL_DIR.mkdir(parents=True, exist_ok=True)

    for base in TOKENS_A:
        for quote in TOKENS_B:
            if base.lower() == quote.lower():
                continue

            print(f"\n{'=' * 50}")
            print(f"{base}<->{quote}")
            print(f"{'=' * 50}")

            try:
                _ = get_token_info(token_map, base)
                _ = get_token_info(token_map, quote)
            except (KeyError, ValueError) as e:
                print(f"Skipping {base}<->{quote}: {e}")
                continue

            trades = fetch_pair(subgraph_url, token_map, base, quote)

            if trades:
                oldest = min(t["timestamp"] for t in trades)
                newest = max(t["timestamp"] for t in trades)
                total_base = sum(t["base_amount"] for t in trades)
                total_quote = sum(t["quote_amount"] for t in trades)
                print(f"Range: {oldest.date()} to {newest.date()}")
                print(f"Volume: {total_base:.2f} {base} / {total_quote:,.0f} {quote}")

            output_path = PARTIAL_DIR / f"{base.lower()}-{quote.lower()}.csv"
            export_csv(trades, output_path, base, quote)
            print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()

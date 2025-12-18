"""
Fetch historical WBTC<->stablecoin trades from CoW Protocol subgraph.

Usage: uv run fetch_trades.py [USDT|USDC|ALL]
"""

import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import httpx
from dotenv import load_dotenv

load_dotenv()

GRAPH_API_KEY = os.getenv("GRAPH_API_KEY")
SUBGRAPH_ID = "8mdwJG7YCSwqfxUbhCypZvoubeZcFVpCHb4zmHhvuKTD"
SUBGRAPH_URL = (
    f"https://gateway.thegraph.com/api/{GRAPH_API_KEY}/subgraphs/id/{SUBGRAPH_ID}"
)

TOKENS = {
    "WBTC": {"address": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599", "decimals": 8},
    "USDT": {"address": "0xdac17f958d2ee523a2206206994597c13d831ec7", "decimals": 6},
    "USDC": {"address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "decimals": 6},
}

PAGE_SIZE = 1000


@dataclass
class Trade:
    id: str
    timestamp: datetime
    direction: str
    base_amount: Decimal
    quote_amount: Decimal
    base_amount_usd: Decimal
    quote_amount_usd: Decimal
    effective_price: Decimal
    tx_hash: str


def query_subgraph(query):
    response = httpx.post(
        SUBGRAPH_URL,
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


def fetch_trades_page(sell_token, buy_token, last_timestamp=None, last_id=None):
    where = f'sellToken_: {{address: "{sell_token}"}}, buyToken_: {{address: "{buy_token}"}}'
    if last_timestamp is not None and last_id is not None:
        where = f'{where}, timestamp_lte: {last_timestamp}, id_not: "{last_id}"'

    query = f"""
    {{ trades(first: {PAGE_SIZE}, orderBy: timestamp, orderDirection: desc, where: {{{where}}}) {{
        id timestamp sellAmount buyAmount sellAmountUsd buyAmountUsd txHash
    }} }}
    """
    return query_subgraph(query).get("data", {}).get("trades", [])


def fetch_all_trades(base, quote, base_decimals, quote_decimals, direction):
    all_trades = []
    last_timestamp, last_id = None, None
    page = 0
    is_base_sell = direction.startswith("WBTC_TO_")

    sell_addr = TOKENS["WBTC"]["address"] if is_base_sell else TOKENS[quote]["address"]
    buy_addr = TOKENS[quote]["address"] if is_base_sell else TOKENS["WBTC"]["address"]

    while True:
        page += 1
        print(f"  Page {page} ({direction})...", end=" ", flush=True)
        trades = fetch_trades_page(sell_addr, buy_addr, last_timestamp, last_id)

        if not trades:
            print("done")
            break
        print(f"{len(trades)} trades")

        for t in trades:
            ts = datetime.fromtimestamp(int(t["timestamp"]))
            sell_amt, buy_amt = Decimal(t["sellAmount"]), Decimal(t["buyAmount"])
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

            base_amount = base_raw / Decimal(10**base_decimals)
            quote_amount = quote_raw / Decimal(10**quote_decimals)
            price = quote_amount / base_amount if base_amount > 0 else Decimal(0)

            all_trades.append(
                Trade(
                    id=t["id"],
                    timestamp=ts,
                    direction=direction,
                    base_amount=base_amount,
                    quote_amount=quote_amount,
                    base_amount_usd=base_usd,
                    quote_amount_usd=quote_usd,
                    effective_price=price,
                    tx_hash=t["txHash"],
                )
            )

        last_timestamp, last_id = int(trades[-1]["timestamp"]), trades[-1]["id"]
        if len(trades) < PAGE_SIZE:
            break

    return all_trades


def export_csv(trades, filename, base, quote):
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        q = quote.lower()
        writer.writerow(
            [
                "timestamp",
                "direction",
                "wbtc_amount",
                f"{q}_amount",
                f"effective_price_{q}_per_wbtc",
                "wbtc_amount_usd",
                f"{q}_amount_usd",
                "tx_hash",
                "trade_id",
            ]
        )
        for t in trades:
            writer.writerow(
                [
                    t.timestamp.isoformat(),
                    t.direction,
                    f"{t.base_amount:.8f}",
                    f"{t.quote_amount:.6f}",
                    f"{t.effective_price:.2f}",
                    f"{t.base_amount_usd:.2f}",
                    f"{t.quote_amount_usd:.2f}",
                    t.tx_hash,
                    t.id,
                ]
            )


def fetch_pair(base, quote):
    base_info, quote_info = TOKENS[base], TOKENS[quote]

    print(f"Fetching {base} -> {quote}...")
    fwd = fetch_all_trades(
        base, quote, base_info["decimals"], quote_info["decimals"], f"{base}_TO_{quote}"
    )
    print(f"  Total: {len(fwd)}")

    print(f"Fetching {quote} -> {base}...")
    rev = fetch_all_trades(
        base, quote, base_info["decimals"], quote_info["decimals"], f"{quote}_TO_{base}"
    )
    print(f"  Total: {len(rev)}")

    all_trades = fwd + rev
    all_trades.sort(key=lambda t: t.timestamp, reverse=True)
    return all_trades


def main():
    pair = sys.argv[1].upper() if len(sys.argv) > 1 else "ALL"

    if pair == "USDC":
        pairs = [("WBTC", "USDC")]
    elif pair == "USDT":
        pairs = [("WBTC", "USDT")]
    elif pair == "ALL":
        pairs = [("WBTC", "USDT"), ("WBTC", "USDC")]
    else:
        print(f"Usage: uv run fetch_trades.py [USDT|USDC|ALL]")
        sys.exit(1)

    for base, quote in pairs:
        print(f"\n{'=' * 50}")
        print(f"{base}<->{quote}")
        print(f"{'=' * 50}")

        trades = fetch_pair(base, quote)

        if trades:
            oldest, newest = (
                min(t.timestamp for t in trades),
                max(t.timestamp for t in trades),
            )
            total_base = sum(t.base_amount for t in trades)
            total_quote = sum(t.quote_amount for t in trades)
            print(f"Range: {oldest.date()} to {newest.date()}")
            print(f"Volume: {total_base:.2f} {base} / {total_quote:,.0f} {quote}")

        output = f"wbtc_{quote.lower()}_trades.csv"
        export_csv(trades, output, base, quote)
        print(f"Saved to {output}")


if __name__ == "__main__":
    main()

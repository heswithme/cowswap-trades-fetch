# CoW Protocol Trade Fetcher

Fetch historical trades from [CoW Protocol](https://cow.fi) via TheGraph subgraph.

## Setup

```bash
# Get API key from https://thegraph.com/studio/apikeys/
echo "GRAPH_API_KEY=your_key_here" > .env

# Install deps
uv sync
```

## Configuration

All parameters live in the script headers:

- `fetch_trades.py`: edit `TOKENS_A` and `TOKENS_B` to pick pairs to fetch
- `merge_trades.py`: edit `ASSET_GROUPS` and `TOKENS_B` to pick which partial files to merge

Token addresses/decimals live in `token-addresses.json`.

## Usage

```bash
# Fetch all A-B combinations into data/partial/
uv run fetch_trades.py

# Merge partial files into data/<asset>usd.csv (e.g. data/btcusd.csv)
uv run merge_trades.py
```

## Output

**Raw (per-pair) files:**
- `data/partial/<tokenA>-<tokenB>.csv` (e.g. `data/partial/eth-usdc.csv`)

**Merged (per-asset) files:**
- `data/<asset>usd.csv` (e.g. `data/btcusd.csv`)

Merged columns:
- `unix_timestamp` - epoch time
- `date` - human readable
- `direction` - BUY (USD→crypto) or SELL (crypto→USD)
- `<asset>_amount` - crypto amount
- `usd_amount`, `price` - stablecoin amount and price
- `total_usd_volume` - trade size in USD
- `source` - usdt or usdc

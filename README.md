# CoW Protocol WBTC Trades

Fetch historical WBTC<->USDT/USDC trades from [CoW Protocol](https://cow.fi) via TheGraph subgraph.

## Setup

```bash
# Get API key from https://thegraph.com/studio/apikeys/
echo "GRAPH_API_KEY=your_key_here" > .env

# Install deps
uv sync
```

## Usage

```bash
# Fetch trades (creates wbtc_usdt_trades.csv and wbtc_usdc_trades.csv)
uv run fetch_trades.py          # both pairs
uv run fetch_trades.py USDT     # only USDT
uv run fetch_trades.py USDC     # only USDC

# Merge into single file (creates btcusd-cowswap.csv)
uv run merge_trades.py
```

## Configuration

Edit `merge_trades.py` to filter:

```python
START_DATE = None      # e.g., "2024-01-01"
END_DATE = None        # e.g., "2024-12-31"  
MIN_VOLUME_USD = 100   # minimum trade size
```

## Output

`btcusd-cowswap.csv` columns:
- `unix_timestamp` - epoch time
- `date` - human readable
- `direction` - BUY (USD→WBTC) or SELL (WBTC→USD)
- `wbtc_amount`, `usd_amount`, `price`
- `total_usd_volume` - trade size in USD
- `source` - USDT or USDC

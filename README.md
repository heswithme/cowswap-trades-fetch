# CoW Protocol Trade Fetcher

Fetch historical WBTC and WETH trades from [CoW Protocol](https://cow.fi) via TheGraph subgraph.

## Setup

```bash
# Get API key from https://thegraph.com/studio/apikeys/
echo "GRAPH_API_KEY=your_key_here" > .env

# Install deps
uv sync
```

## Usage

```bash
# Fetch WBTC trades
uv run fetch_trades.py WBTC          # WBTC vs USDT+USDC
uv run fetch_trades.py WBTC USDT     # WBTC vs USDT only
uv run fetch_trades.py WBTC USDC     # WBTC vs USDC only

# Fetch WETH trades  
uv run fetch_trades.py WETH          # WETH vs USDT+USDC
uv run fetch_trades.py WETH USDT     # WETH vs USDT only
uv run fetch_trades.py WETH USDC     # WETH vs USDC only

# Merge into single file
uv run merge_trades.py
```

## Configuration

Edit `merge_trades.py` to configure:

```python
CRYPTO = "WBTC"        # "WBTC" or "WETH"
START_DATE = None      # e.g., "2024-01-01"
END_DATE = None        # e.g., "2024-12-31"  
MIN_VOLUME_USD = 100   # minimum trade size
```

## Output

**Raw fetch files:**
- `wbtc_usdt_trades.csv`, `wbtc_usdc_trades.csv`
- `weth_usdt_trades.csv`, `weth_usdc_trades.csv`

**Merged files:**
- `btcusd-cowswap.csv` (when CRYPTO="WBTC")
- `ethusd-cowswap.csv` (when CRYPTO="WETH")

Columns:
- `unix_timestamp` - epoch time
- `date` - human readable
- `direction` - BUY (USD→crypto) or SELL (crypto→USD)
- `wbtc_amount` or `weth_amount` - crypto amount
- `usd_amount`, `price` - stablecoin amount and price
- `total_usd_volume` - trade size in USD
- `source` - USDT or USDC

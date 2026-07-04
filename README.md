# XLuckyMiner

A Python-based solo Bitcoin miner that uses OpenCL for GPU hashing. Designed to be lightweight and "lucky" - it mines directly against your own Bitcoin node.

## Features
- **Solo Mining**: Connects directly to your local Bitcoin Core node via RPC.
- **GPU Mining**: Uses PyOpenCL to leverage your GPU (works with AMD/ROCm, NVIDIA, and any OpenCL device).
- **Load Limiting**: Configurable GPU load limit (default 30%) to allow for background usage.
- **Auto Start/Pause (Watchdog)**: `watchdog.py` starts the miner when the GPU has been idle for a while and pauses it automatically when another app needs the GPU. GPU usage is read via `amdsmi` (with a `rocm-smi` fallback).
- **Telegram Notifications**: Get alerts on startup and if you find a block. Messages are network-aware, so test-network blocks are clearly marked as `[TEST]` and never look like a real reward.

## Prerequisites
1. **Bitcoin Node**: You need a fully synced Bitcoin node (e.g., Bitcoin Core) running with RPC enabled.
   - Add the following to your `bitcoin.conf`:
     ```
     server=1
     rpcuser=yourusername
     rpcpassword=yourpassword
     rpcallowip=127.0.0.1
     ```
2. **Python 3.8+**
3. **OpenCL Drivers**: Ensure your GPU drivers are installed and support OpenCL.

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure the miner:
   - **Main Config**:
     - Rename `config_sample.py` to `config.py`.
     - Edit `config.py`:
       - **RPC Settings**: Enter your node's URL, user, and password.
       - **Wallet**: Set `WALLET_ADDRESS` to your Bitcoin address. **This is where your rewards will go if you find a block.**
       - **Load Limit**: Set `GPU_LOAD_LIMIT_PERCENT` (default 30).
       - **Watchdog (optional)**: `PAUSE_THRESHOLD_PERCENT` (pause when total GPU usage exceeds this — keep it well above the load limit), `IDLE_THRESHOLD_PERCENT` and `IDLE_WAIT_MINUTES` (start once the GPU has been idle this long).
   - **Telegram Notifications (Optional)**:
     - Rename `telegram_config_sample.py` to `telegram_config.py`.
     - Edit `telegram_config.py` with your Bot Token and Chat ID.

> `config.py` and `telegram_config.py` are git-ignored, so your RPC password, wallet, and bot token are never committed.

## How to Receive Funds
1. **Create a Wallet**: Use any Bitcoin wallet (e.g., Electrum, Sparrow, or Bitcoin Core itself) to generate a Receive Address.
2. **Configure**: Copy this address into `config.py` as `WALLET_ADDRESS`.
3. **Mining**: When the miner runs, it attempts to solve a block.
4. **Payout**: If you solve a block (extremely rare!), the network will credit the block reward (currently 3.125 BTC + fees - 2025) directly to your address.
   - **Source**: The transaction will appear as a **Coinbase Transaction** (newly generated coins). It does **not** come from a specific sender address.
   - *Note*: This miner is a solo miner. You do not need to register with any pool. You are competing directly against the global network.

## Usage
Run the miner directly:
```bash
python main.py
```

Or let the watchdog manage it (start when idle, pause when the GPU is busy):
```bash
python watchdog.py         # waits for the GPU to be idle before starting
python watchdog.py --now    # start immediately, skipping the idle wait
```

## Disclaimer
The odds of finding a block solo with a single GPU are astronomically low. This project is for educational purposes and for those who want to buy a lottery ticket with their spare GPU cycles.

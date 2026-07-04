# XLuckyMiner Configuration
### RENOMBRAR A config.py <------------------------------------------------------------- IMPORTANTE ------------------------

# Bitcoin Node RPC Settings
RPC_URL = "http://127.0.0.1:8332"
RPC_USER = "rpcuser"
RPC_PASSWORD = "rpcpassword"

# Mining Settings
# Target load for the miner ITSELF, as a % of GPU time (duty cycle).
# miner/hashing.py sleeps between batches so the miner averages roughly this load.
GPU_LOAD_LIMIT_PERCENT = 30

# Watchdog Settings (watchdog.py) -- auto start/pause based on GPU usage.
# Pause the miner if TOTAL GPU usage goes above this (another app is using the GPU).
# Must be comfortably ABOVE GPU_LOAD_LIMIT_PERCENT, or the miner would pause itself.
PAUSE_THRESHOLD_PERCENT = 90
# Only pause if usage stays above the threshold this many seconds straight,
# so brief spikes don't pause (and later restart) the miner.
PAUSE_SUSTAIN_SECONDS = 15
# "Idle" means TOTAL GPU usage below this (only checked while the miner is off).
IDLE_THRESHOLD_PERCENT = 20
# Minutes of continuous idle before (re)starting the miner.
IDLE_WAIT_MINUTES = 10
# How often the watchdog samples GPU usage (seconds).
CHECK_INTERVAL_SECONDS = 5
# Which GPU to watch (index, matches rocm-smi cardN / amdsmi handle order).
GPU_INDEX = 0

# Wallet Settings
# Your Bitcoin Address to receive rewards (replace with your own address)
WALLET_ADDRESS = "YOUR_BITCOIN_ADDRESS_HERE"

# OpenCL Settings
# Platform and Device Index (default to 0, change if you have multiple GPUs/Platforms)
OPENCL_PLATFORM_INDEX = 0
OPENCL_DEVICE_INDEX = 0

# Work Size (Adjust based on GPU capability)
GLOBAL_WORK_SIZE = 1024 * 1024  # Number of hashes per batch
LOCAL_WORK_SIZE = 256           # Work group size

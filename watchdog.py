#!/usr/bin/env python3
"""
XLuckyMiner Watchdog (Linux / ROCm)

Control loop:
  - Miner OFF: if GPU usage stays below IDLE_THRESHOLD_PERCENT continuously for
    IDLE_WAIT_MINUTES, start the miner.
  - Miner ON:  the miner self-throttles to ~GPU_LOAD_LIMIT_PERCENT (see
    miner/hashing.py). If the TOTAL GPU usage rises above PAUSE_THRESHOLD_PERCENT
    (i.e. another app started using the GPU), stop the miner and restart the
    idle countdown.

GPU usage is read via the amdsmi Python API when available, falling back to
parsing `rocm-smi --showuse --json`. Readings are averaged over several quick
samples because the miner's duty-cycle throttle makes instantaneous usage bursty.
"""

import subprocess
import time
import os
import sys
import json
import shutil
import logging

# ==========================================
# CONFIGURATION
# ==========================================
import config

# The miner's own target load (used by miner/hashing.py to throttle via sleep).
GPU_LOAD_LIMIT_PERCENT  = getattr(config, "GPU_LOAD_LIMIT_PERCENT", 30)

# Pause the miner if TOTAL GPU usage rises above this (must be > GPU_LOAD_LIMIT_PERCENT).
PAUSE_THRESHOLD_PERCENT = getattr(config, "PAUSE_THRESHOLD_PERCENT", 60)

# Only pause if usage stays above the threshold for this many seconds straight.
# This ignores brief spikes so the miner isn't paused (and later restarted) on noise.
PAUSE_SUSTAIN_SECONDS   = getattr(config, "PAUSE_SUSTAIN_SECONDS", 15)

# "Idle" means TOTAL GPU usage below this (checked only while the miner is OFF).
IDLE_THRESHOLD_PERCENT  = getattr(config, "IDLE_THRESHOLD_PERCENT", 20)

# Minutes of continuous idle before (re)starting the miner.
IDLE_WAIT_MINUTES       = getattr(config, "IDLE_WAIT_MINUTES", 10)

# How often to evaluate GPU usage.
CHECK_INTERVAL_SECONDS  = getattr(config, "CHECK_INTERVAL_SECONDS", 5)

# Which GPU to watch (index).
GPU_INDEX               = getattr(config, "GPU_INDEX", 0)

MINER_SCRIPT = "main.py"
# ==========================================

# Optional Telegram notifications
try:
    import telegram_config as tg_config
    from miner.telegram_sender import TelegramSender
    TELEGRAM_ENABLED = True
except ImportError:
    TELEGRAM_ENABLED = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [WATCHDOG] - %(message)s',
    datefmt='%H:%M:%S'
)


# ------------------------------------------------------------------
# GPU usage backends: amdsmi (preferred) -> rocm-smi --json (fallback)
# ------------------------------------------------------------------
def init_backend():
    """Return (kind, context) for reading GPU usage, or (None, None)."""
    # Preferred: amdsmi Python API (in-process, cheap to poll).
    try:
        import amdsmi
        amdsmi.amdsmi_init()
        handles = amdsmi.amdsmi_get_processor_handles()
        if handles:
            logging.info("GPU backend: amdsmi (Python API)")
            return "amdsmi", (amdsmi, handles)
    except Exception as e:
        logging.info(f"amdsmi unavailable ({e.__class__.__name__}); trying rocm-smi.")

    # Fallback: rocm-smi CLI with JSON output.
    if shutil.which("rocm-smi"):
        logging.info("GPU backend: rocm-smi --json")
        return "rocm-smi", None

    return None, None


def read_gpu_once(backend):
    """Single instantaneous GPU usage reading (0-100). Raises on failure."""
    kind, ctx = backend

    if kind == "amdsmi":
        amdsmi, handles = ctx
        handle = handles[GPU_INDEX]
        activity = amdsmi.amdsmi_get_gpu_activity(handle)
        # Key casing changed across amdsmi versions; accept both.
        val = activity.get("gfx_activity", activity.get("GFX_ACTIVITY"))
        return float(val)

    if kind == "rocm-smi":
        result = subprocess.run(
            ["rocm-smi", "--showuse", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        card = data.get(f"card{GPU_INDEX}") or next(iter(data.values()))
        for key, value in card.items():
            if "use" in key.lower():  # "GPU use (%)"
                return float(str(value).strip().rstrip("%"))
        raise ValueError(f"No usage field in rocm-smi output: {card}")

    raise RuntimeError("No GPU backend available")


def get_gpu_usage(backend, samples=4, gap=0.25):
    """Average several quick readings to smooth the miner's bursty duty cycle."""
    values = []
    for _ in range(samples):
        try:
            values.append(read_gpu_once(backend))
        except Exception:
            pass
        time.sleep(gap)
    return sum(values) / len(values) if values else 0.0


def stop_miner(proc, telegram, reason):
    logging.warning(f"\n{reason}")
    if telegram:
        telegram.send_message(reason)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    logging.info("Miner stopped.")


def main():
    # --- Sanity-check thresholds so the miner can't pause itself ---
    if PAUSE_THRESHOLD_PERCENT <= GPU_LOAD_LIMIT_PERCENT:
        logging.warning(
            f"PAUSE_THRESHOLD_PERCENT ({PAUSE_THRESHOLD_PERCENT}%) <= "
            f"GPU_LOAD_LIMIT_PERCENT ({GPU_LOAD_LIMIT_PERCENT}%): the miner's own "
            f"load may trip the pause. Set PAUSE_THRESHOLD_PERCENT higher."
        )
    if IDLE_THRESHOLD_PERCENT >= PAUSE_THRESHOLD_PERCENT:
        logging.warning(
            f"IDLE_THRESHOLD_PERCENT ({IDLE_THRESHOLD_PERCENT}%) should be well "
            f"below PAUSE_THRESHOLD_PERCENT ({PAUSE_THRESHOLD_PERCENT}%)."
        )

    backend = init_backend()
    if backend[0] is None:
        logging.error(
            "No GPU usage backend found. Install 'amdsmi' (sudo dnf install amdsmi) "
            "or ensure 'rocm-smi' is on PATH."
        )
        return

    logging.info(
        f"Watchdog started. Mine@~{GPU_LOAD_LIMIT_PERCENT}% | "
        f"start when idle<{IDLE_THRESHOLD_PERCENT}% for {IDLE_WAIT_MINUTES}m | "
        f"pause when total>{PAUSE_THRESHOLD_PERCENT}% sustained {PAUSE_SUSTAIN_SECONDS}s"
    )

    telegram = None
    if TELEGRAM_ENABLED:
        try:
            telegram = TelegramSender(tg_config.TELEGRAM_BOT_TOKEN, tg_config.TELEGRAM_CHAT_ID)
        except Exception as e:
            logging.error(f"Telegram init failed: {e}")

    # --now / -n skips the initial idle wait.
    force_start = len(sys.argv) > 1 and sys.argv[1] in ("--now", "-n")
    if force_start:
        logging.info("Force start (--now): skipping idle wait.")
        last_busy_time = time.time() - (IDLE_WAIT_MINUTES * 60) - 10
    else:
        last_busy_time = time.time()

    miner_process = None
    busy_since = None  # when the GPU first crossed the pause threshold (streak start)

    try:
        while True:
            usage = get_gpu_usage(backend)

            if miner_process is None:
                # Miner OFF: decide whether to start, using the IDLE threshold.
                if usage >= IDLE_THRESHOLD_PERCENT:
                    last_busy_time = time.time()  # not idle -> restart countdown
                    print(f"Status: BUSY  (GPU: {usage:4.1f}%) | waiting for idle...   ", end='\r')
                else:
                    minutes_idle = (time.time() - last_busy_time) / 60.0
                    print(f"Status: IDLE  (GPU: {usage:4.1f}%) | {minutes_idle:.1f}/{IDLE_WAIT_MINUTES}m   ", end='\r')
                    if minutes_idle >= IDLE_WAIT_MINUTES:
                        msg = f"🟢 GPU idle {minutes_idle:.1f}m. Starting miner."
                        logging.info(f"\n{msg}")
                        if telegram:
                            telegram.send_message(msg)
                        miner_process = subprocess.Popen([sys.executable, MINER_SCRIPT])
                        logging.info(f"Miner PID: {miner_process.pid}")
                        busy_since = None
            else:
                # Miner ON.
                if miner_process.poll() is not None:
                    logging.warning("\nMiner process died unexpectedly. Resetting timer.")
                    if telegram:
                        telegram.send_message("⚠️ Miner process died. Resetting watchdog timer.")
                    miner_process = None
                    last_busy_time = time.time()
                    busy_since = None
                elif usage >= PAUSE_THRESHOLD_PERCENT:
                    # Only pause once usage has stayed high for PAUSE_SUSTAIN_SECONDS
                    # straight (ignore brief spikes).
                    if busy_since is None:
                        busy_since = time.time()
                    held = time.time() - busy_since
                    if held >= PAUSE_SUSTAIN_SECONDS:
                        stop_miner(
                            miner_process, telegram,
                            f"🛑 GPU busy ({usage:.1f}% for {held:.0f}s). Pausing miner.",
                        )
                        miner_process = None
                        last_busy_time = time.time()  # restart the idle countdown
                        busy_since = None
                    else:
                        print(f"Status: HIGH   (GPU: {usage:4.1f}%) | confirming {held:.0f}/{PAUSE_SUSTAIN_SECONDS}s   ", end='\r')
                else:
                    busy_since = None  # dipped below threshold -> reset the streak
                    print(f"Status: MINING (GPU: {usage:4.1f}%) | monitoring...      ", end='\r')

            time.sleep(CHECK_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logging.info("\nWatchdog shutting down (Ctrl+C).")
        if miner_process:
            miner_process.terminate()


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()

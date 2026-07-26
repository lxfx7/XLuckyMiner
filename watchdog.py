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
import signal
import logging
import traceback
from collections import deque

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
MINER_LOG = os.path.join("logs", "xluckyminer.log")

# A miner that dies sooner than this after starting is treated as crash-looping;
# the restart delay then grows so a broken setup doesn't spam Telegram.
FAST_EXIT_SECONDS = 120
CRASH_BACKOFF_BASE_SECONDS = 60
CRASH_BACKOFF_MAX_SECONDS = 1800
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


def notify(telegram, text):
    """Best-effort Telegram notification; never breaks the watchdog loop."""
    if not telegram:
        return
    try:
        telegram.send_message(text)
    except Exception as e:
        logging.error(f"Telegram notification failed: {e}")


def miner_log_tail(lines=12):
    """Last lines of the miner log, to explain a crash in the alert itself."""
    try:
        with open(MINER_LOG, "r", encoding="utf-8", errors="replace") as f:
            return "".join(deque(f, maxlen=lines)).strip()
    except Exception as e:
        return f"(could not read {MINER_LOG}: {e})"


def stop_miner(proc, telegram, reason):
    logging.warning(f"\n{reason}")
    notify(telegram, reason)
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

    telegram = None
    if TELEGRAM_ENABLED:
        try:
            telegram = TelegramSender(tg_config.TELEGRAM_BOT_TOKEN, tg_config.TELEGRAM_CHAT_ID)
        except Exception as e:
            logging.error(f"Telegram init failed: {e}")

    backend = init_backend()
    if backend[0] is None:
        msg = ("No GPU usage backend found. Install 'amdsmi' (sudo dnf install amdsmi) "
               "or ensure 'rocm-smi' is on PATH.")
        logging.error(msg)
        notify(telegram, f"💥 XLuckyMiner watchdog could not start\n{msg}")
        sys.exit(1)

    logging.info(
        f"Watchdog started. Mine@~{GPU_LOAD_LIMIT_PERCENT}% | "
        f"start when idle<{IDLE_THRESHOLD_PERCENT}% for {IDLE_WAIT_MINUTES}m | "
        f"pause when total>{PAUSE_THRESHOLD_PERCENT}% sustained {PAUSE_SUSTAIN_SECONDS}s"
    )

    # --now / -n skips the initial idle wait.
    force_start = len(sys.argv) > 1 and sys.argv[1] in ("--now", "-n")
    if force_start:
        logging.info("Force start (--now): skipping idle wait.")
        last_busy_time = time.time() - (IDLE_WAIT_MINUTES * 60) - 10
    else:
        last_busy_time = time.time()

    miner_process = None
    miner_started_at = 0.0
    busy_since = None  # when the GPU first crossed the pause threshold (streak start)
    fast_exits = 0     # consecutive crash-loop exits
    hold_until = 0.0   # don't start the miner again before this time

    try:
        while True:
            usage = get_gpu_usage(backend)

            if miner_process is None:
                # Miner OFF: decide whether to start, using the IDLE threshold.
                if usage >= IDLE_THRESHOLD_PERCENT:
                    last_busy_time = time.time()  # not idle -> restart countdown
                    print(f"Status: BUSY  (GPU: {usage:4.1f}%) | waiting for idle...   ", end='\r')
                elif time.time() < hold_until:
                    wait_left = hold_until - time.time()
                    print(f"Status: HELD  (GPU: {usage:4.1f}%) | crash backoff {wait_left:.0f}s   ", end='\r')
                else:
                    minutes_idle = (time.time() - last_busy_time) / 60.0
                    print(f"Status: IDLE  (GPU: {usage:4.1f}%) | {minutes_idle:.1f}/{IDLE_WAIT_MINUTES}m   ", end='\r')
                    if minutes_idle >= IDLE_WAIT_MINUTES:
                        msg = f"🟢 GPU idle {minutes_idle:.1f}m. Starting miner."
                        logging.info(f"\n{msg}")
                        notify(telegram, msg)
                        miner_process = subprocess.Popen([sys.executable, MINER_SCRIPT])
                        miner_started_at = time.time()
                        logging.info(f"Miner PID: {miner_process.pid}")
                        busy_since = None
            else:
                # Miner ON.
                if miner_process.poll() is not None:
                    code = miner_process.returncode
                    ran_for = time.time() - miner_started_at

                    # Back off on a crash loop so a broken node/GPU doesn't
                    # produce a Telegram alert every few minutes.
                    if ran_for < FAST_EXIT_SECONDS:
                        fast_exits += 1
                        backoff = min(
                            CRASH_BACKOFF_BASE_SECONDS * (2 ** (fast_exits - 1)),
                            CRASH_BACKOFF_MAX_SECONDS,
                        )
                    else:
                        fast_exits = 0
                        backoff = 0
                    hold_until = time.time() + backoff

                    logging.warning(
                        f"\nMiner exited (code {code}) after {ran_for:.0f}s. "
                        f"Retry hold: {backoff}s."
                    )
                    retry_note = (
                        f"Retrying once the GPU is idle (+{backoff}s backoff)."
                        if backoff else "Retrying once the GPU is idle."
                    )
                    notify(
                        telegram,
                        f"⚠️ XLuckyMiner stopped — process exited with code {code} "
                        f"after {ran_for:.0f}s.\n{retry_note}\n\nLast log lines:\n"
                        f"{miner_log_tail()}"
                    )
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
    except SystemExit:
        # SIGTERM (logout, shutdown, systemctl stop): expected, not a crash.
        logging.info("\nWatchdog shutting down (SIGTERM).")
        notify(telegram, "🛑 XLuckyMiner watchdog stopped (SIGTERM).")
        if miner_process:
            miner_process.terminate()
        raise
    except Exception as e:
        # Nothing else supervises the watchdog, so an unhandled exception here
        # silently ends all mining. Always report it.
        logging.exception("Watchdog crashed")
        notify(
            telegram,
            f"💥 XLuckyMiner WATCHDOG CRASHED — mining has stopped.\n"
            f"{type(e).__name__}: {e}\n\n{traceback.format_exc()[-1200:]}"
        )
        if miner_process:
            miner_process.terminate()
        sys.exit(1)


def _on_sigterm(signum, frame):
    raise SystemExit(0)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    signal.signal(signal.SIGTERM, _on_sigterm)
    main()

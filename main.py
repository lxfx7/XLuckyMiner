import time
import struct
import binascii
import logging
import os
import numpy as np
from miner.network import BitcoindClient
from miner.hashing import GPUMiner
from miner.utils import swap_endian_word, hex_to_bytes, bytes_to_hex, create_coinbase, calculate_merkle_root, double_sha256, sha256_transform, bits_to_target
from config import GLOBAL_WORK_SIZE, WALLET_ADDRESS
try:
    import telegram_config as tg_config
    from miner.telegram_sender import TelegramSender
except ImportError:
    tg_config = None
    TelegramSender = None

import sys

# Dispose logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "xluckyminer.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout) # Keep console output
    ]
)

def main():
    logging.info(f"XLuckyMiner Starting... Payout Address: {WALLET_ADDRESS}")
    
    # Initialize Telegram Sender
    telegram_sender = None
    if tg_config and hasattr(tg_config, 'TELEGRAM_BOT_TOKEN'):
        telegram_sender = TelegramSender(tg_config.TELEGRAM_BOT_TOKEN, tg_config.TELEGRAM_CHAT_ID)
        telegram_sender.send_message(f"🚀 XLuckyMiner Started!\nAddress: `{WALLET_ADDRESS}`")

    client = BitcoindClient()
    
    # Check connection
    info = client.get_blockchain_info()
    if not info:
        logging.error("Failed to connect to Bitcoin Node. Check config.py and ensure node is running.")
        return
    chain = info.get('chain', 'unknown')
    is_mainnet = (chain == 'main')
    logging.info(f"Connected to Bitcoin Node. Chain: {chain}, Blocks: {info.get('blocks')}")
    if not is_mainnet:
        logging.warning(f"Running on '{chain}' — this is a TEST network, coins are NOT real BTC.")

    # Validate Address and get ScriptPubKey
    addr_info = client.validate_address(WALLET_ADDRESS)
    if not addr_info or not addr_info.get('isvalid'):
        logging.error(f"Invalid Wallet Address: {WALLET_ADDRESS}")
        return
    
    script_pubkey = addr_info.get('scriptPubKey')
    if not script_pubkey:
        # Some versions return it in 'embedded' or different fields?
        # Usually it is 'scriptPubKey' (hex string) or 'scriptPubKey' (object with hex)?
        # validateaddress details: 'scriptPubKey' is hex string.
        logging.error(f"Could not get scriptPubKey for {WALLET_ADDRESS}")
        if 'scriptPubKey' in addr_info: 
             # Check if it's nested dictionary? No, usually hex string.
             pass
        # Fallback to outputting info to debug
        logging.error(f"Addr Info: {addr_info}")
        return
        
    logging.info(f"ScriptPubKey: {script_pubkey}")
    
    try:
        miner = GPUMiner()
        logging.info(f"GPU Initialized: {miner.device.name}")
    except Exception as e:
        logging.error(f"Failed to initialize GPU Miner: {e}")
        return

    logging.info("Starting Mining Loop...")
    while True:
        # 1. Get Block Template
        template = client.get_block_template()
        if not template:
            print("Failed to get block template. Retrying in 5s...")
            time.sleep(5)
            continue
        
        # 2. Parse Template
        version = template['version']
        prev_hash = template['previousblockhash'] # Big Endian Hex
        
        # Handle Merkle Root
        if 'merkleroot' in template:
            merkle_root = template['merkleroot']
        else:
            # Calculate Merkle Root
            # 1. Create Coinbase
            coinbase_val = template['coinbasevalue']
            height = template['height']
            # We use a simple extra nonce
            coinbase_tx = create_coinbase(height, coinbase_val, script_pubkey)
            
            # 2. Hash Coinbase
            coinbase_hash = double_sha256(coinbase_tx)
            # Convert to Big Endian Hex for list
            coinbase_hash_hex = binascii.hexlify(coinbase_hash[::-1]).decode('utf-8')
            
            # 3. Get tx hashes
            tx_hashes = [tx['hash'] for tx in template['transactions']]
            
    # 4. Calculate Root
            merkle_root = calculate_merkle_root([coinbase_hash_hex] + tx_hashes)
            
        cur_time = template['curtime']
        bits = template['bits']
        
        # 3. Prepare Header Data for GPU
        # Header Layout: Version (4) | PrevHash (32) | MerkleRoot (32) | Time (4) | Bits (4) | Nonce (4)
        
        # Construct full header with dummy nonce (Little Endian fields)
        ver_bytes = struct.pack('<I', version)
        prev_bytes = hex_to_bytes(prev_hash)[::-1]
        merkle_bytes = hex_to_bytes(merkle_root)[::-1]
        time_bytes = struct.pack('<I', cur_time)
        bits_bytes = hex_to_bytes(bits)[::-1]
        nonce_bytes = struct.pack('<I', 0)
        
        header_pre = ver_bytes + prev_bytes + merkle_bytes + time_bytes + bits_bytes + nonce_bytes
        
        # Calculate Midstate
        # SHA256 transform of first 64 bytes.
        chunk1 = header_pre[:64]
        midstate_tuple = sha256_transform(chunk1)
        midstate = np.array(midstate_tuple, dtype=np.uint32)
        
        # Prepare Data Tail
        # Bytes 64-79: Merkle[28:32] + Time + Bits + Nonce
        merkle_tail = merkle_bytes[28:]
        
        # Pack into uints (Little Endian)
        data_tail = np.zeros(4, dtype=np.uint32)
        data_tail[0] = struct.unpack('>I', merkle_tail)[0]
        data_tail[1] = struct.unpack('>I', time_bytes)[0]
        data_tail[2] = struct.unpack('>I', bits_bytes)[0]
        data_tail[3] = 0 # Nonce placeholder
        
        start_nonce = 0
        while start_nonce < 0xFFFFFFFF:
            # Measure time for hashrate calculation
            batch_start_time = time.time()
            found_nonce = miner.mine_batch(midstate, data_tail, start_nonce)
            batch_duration = time.time() - batch_start_time
            
            # Calculate metrics
            if batch_duration > 0:
                hashrate = GLOBAL_WORK_SIZE / batch_duration
            else:
                hashrate = 0
                
            # Format hashrate
            if hashrate >= 1e15:
                hr_str = f"{hashrate/1e15:.2f} PH/s"
            elif hashrate >= 1e12:
                hr_str = f"{hashrate/1e12:.2f} TH/s"
            elif hashrate >= 1e9:
                hr_str = f"{hashrate/1e9:.2f} GH/s"
            elif hashrate >= 1e6:
                hr_str = f"{hashrate/1e6:.2f} MH/s"
            elif hashrate >= 1e3:
                hr_str = f"{hashrate/1e3:.2f} KH/s"
            else:
                hr_str = f"{hashrate:.2f} H/s"
            
            print(f"Mining: {hr_str} | Nonce {start_nonce}...", end='\r')
            
            if found_nonce:
                # Re-create the header with the found nonce
                final_nonce_bytes = struct.pack('<I', found_nonce)
                full_header = ver_bytes + prev_bytes + merkle_bytes + time_bytes + bits_bytes + final_nonce_bytes
                
                # Verify Difficulty Locally
                # Calculate Hash (Double SHA256 of header)
                block_hash = double_sha256(full_header)
                # Reverse for Big Endian integer comparison (Bitcoin treats hash as Little Endian in wire, Big Endian in number comparison)
                # Actually, standard is: Hash(Header) result is displayed as BE. Target is BE number.
                # double_sha256 returns bytes. block_hash[::-1] is the LE representation? 
                # No. double_sha256 result is the internal byte order.
                # display (hex) is typically reversed.
                # let's be precise.
                # Target check: int(hash_hex) <= target
                # bytes_to_hex(block_hash[::-1]) gives the standard "Block Hash" string.
                
                block_hash_rev = block_hash[::-1]
                block_hash_hex = bytes_to_hex(block_hash_rev)
                block_hash_int = int(block_hash_hex, 16)
                
                target = int(bits_to_target(bits))
                
                if block_hash_int <= target:
                    if is_mainnet:
                        print(f"\n🚀 FOUND WINNING BLOCK! Nonce: {found_nonce}")
                    else:
                        print(f"\n🧪 [TEST · {chain}] Found a block (NOT real BTC). Nonce: {found_nonce}")
                    print(f"Hash: {block_hash_hex}")
                    
                    # Construct Full Block via Utils (or inline here)
                    # Need VarInt for tx count
                    from miner.utils import encode_varint
                    
                    tx_data_hex = []
                    # Coinbase first
                    tx_data_hex.append(bytes_to_hex(coinbase_tx))
                    
                    # Other transactions
                    for tx in template['transactions']:
                        if 'data' in tx:
                            tx_data_hex.append(tx['data'])
                        else:
                            logging.warning(f"Transaction data missing for {tx.get('hash')}, block submission requires it.")
                    
                    num_txs = len(tx_data_hex)
                    varint_tx_count = encode_varint(num_txs)
                    
                    block_hex = bytes_to_hex(full_header) + bytes_to_hex(varint_tx_count) + "".join(tx_data_hex)
                    
                    print(f"Submitting Block... (Size: {len(block_hex)//2} bytes)")
                    submission_result = client.submit_block(block_hex)
                    
                    if submission_result is None: # Standard success is None or 'null'
                       if is_mainnet:
                           msg = f"🎉 BLOCK ACCEPTED! Real reward! Nonce: {found_nonce}"
                       else:
                           msg = f"🧪 [TEST · {chain}] Block accepted on a TEST network — NOT real BTC. Nonce: {found_nonce}"
                       logging.info(f"BLOCK ACCEPTED! (chain={chain})")
                    else:
                       msg = f"⚠️ Block found but submission result: {submission_result} (chain={chain})"
                       logging.error(f"Submission Error: {submission_result}")

                    if telegram_sender:
                        telegram_sender.send_message(msg + f"\nHeader: `{bytes_to_hex(full_header)}`")

                else:
                    # Valid Share (POW OK, but difficulty too low for network)
                    # This confirms the miner is working correctly!
                    print(f"\n⛏️  Found Share (Difficulty too low). Nonce: {found_nonce}")
                    print(f"    Hash: {block_hash_hex[:16]}...")
                    print(f"    Target approx: {hex(target)[:16]}...")
                    logging.info(f"Share found: {found_nonce} (Valid POW, low diff)")
                    
                # We break to refresh template regardless (simple logic)
                break
            
            start_nonce += GLOBAL_WORK_SIZE
            
            # Check if we should refresh (e.g. every 10 seconds or based on nonce progress)
            # For now, just continue until max nonce or limit
            
        print("\nRefreshing Block Template...")

if __name__ == "__main__":
    main()

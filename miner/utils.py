import struct
import binascii

def swap_endian_word(hex_word):
    """Swaps endianness of a 4-byte hex word."""
    # Input: "12345678" -> Output: "78563412"
    return "".join(reversed([hex_word[i:i+2] for i in range(0, len(hex_word), 2)]))

def target_to_bits(target):
    """Converts a target integer to compact 'bits' format."""
    # Simplified version, usually we get 'bits' from getblocktemplate
    pass

def bits_to_target(bits_hex):
    """Converts compact 'bits' format to target integer."""
    bits = int(bits_hex, 16)
    exponent = bits >> 24
    coefficient = bits & 0xffffff
    return coefficient * 256**(exponent - 3)

def hex_to_bytes(hex_str):
    return binascii.unhexlify(hex_str)

def bytes_to_hex(byte_data):
    return binascii.hexlify(byte_data).decode('utf-8')

def construct_block_header(version, prev_block_hash, merkle_root, time, bits, nonce):
    """Constructs the 80-byte block header."""
    # All fields must be little-endian for hashing
    
    # Version: 4 bytes, LE
    version_bytes = struct.pack('<I', version)
    
    # Prev Block Hash: 32 bytes, LE (input is usually BE hex)
    prev_hash_bytes = hex_to_bytes(prev_block_hash)[::-1]
    
    # Merkle Root: 32 bytes, LE (input is usually BE hex)
    merkle_bytes = hex_to_bytes(merkle_root)[::-1]
    
    # Time: 4 bytes, LE
    time_bytes = struct.pack('<I', time)
    
    # Bits: 4 bytes, LE (input is usually hex string)
    bits_bytes = hex_to_bytes(bits)[::-1]
    
    # Nonce: 4 bytes, LE
    nonce_bytes = struct.pack('<I', nonce)
    
    header = version_bytes + prev_hash_bytes + merkle_bytes + time_bytes + bits_bytes + nonce_bytes
    return header

import hashlib

def double_sha256(data):
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def calculate_merkle_root(tx_hashes):
    """Calculates the Merkle Root from a list of transaction hashes (hex strings)."""
    if not tx_hashes:
        raise ValueError("No transactions")
    
    # Convert hex to bytes and reverse to internal byte order (Little Endian)
    hashes = [binascii.unhexlify(h)[::-1] for h in tx_hashes]
    
    while len(hashes) > 1:
        if len(hashes) % 2 != 0:
            hashes.append(hashes[-1])
        new_hashes = []
        for i in range(0, len(hashes), 2):
            concat = hashes[i] + hashes[i+1]
            new_hashes.append(double_sha256(concat))
        hashes = new_hashes
        
    # Return as Big Endian Hex
    return binascii.hexlify(hashes[0][::-1]).decode('utf-8')

def encode_varint(n):
    if n < 0xfd:
        return struct.pack('<B', n)
    elif n <= 0xffff:
        return b'\xfd' + struct.pack('<H', n)
    elif n <= 0xffffffff:
        return b'\xfe' + struct.pack('<I', n)
    else:
        return b'\xff' + struct.pack('<Q', n)

def create_coinbase(height, value, script_pubkey_hex, extranonce=0):
    """Creates a basic Coinbase transaction."""
    # Version 1 (4 bytes, LE)
    ver = struct.pack('<I', 1)
    
    # Input Count (1)
    in_cnt = b'\x01'
    
    # Input: PrevHash (32 bytes 0) + PrevIndex (4 bytes -1)
    prev_hash = b'\x00' * 32
    prev_idx = b'\xff\xff\xff\xff'
    
    # Coinbase Script (Height + ExtraNonce)
    # BIP34: Height must be pushed
    height_bytes = []
    h = height
    while h > 0:
        height_bytes.append(h & 0xff)
        h >>= 8
    # Pad if MSB set to avoid negative number interpretation
    if height_bytes and (height_bytes[-1] & 0x80):
        height_bytes.append(0x00)
    
    height_script = bytes([len(height_bytes)]) + bytes(height_bytes)
    extranonce_bytes = struct.pack('<I', extranonce)
    script_sig = height_script + extranonce_bytes
    
    script_len = encode_varint(len(script_sig))
    
    # Sequence
    seq = b'\xff\xff\xff\xff'
    
    inp = prev_hash + prev_idx + script_len + script_sig + seq
    
    # Output Count (1)
    out_cnt = b'\x01'
    
    # Output
    val = struct.pack('<Q', value)
    spk_bytes = binascii.unhexlify(script_pubkey_hex)
    spk_len = encode_varint(len(spk_bytes))
    
    out = val + spk_len + spk_bytes
    
    # Locktime
    lock = b'\x00\x00\x00\x00'
    
    return ver + in_cnt + inp + out_cnt + out + lock

# SHA-256 Constants
K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
]

def rotr(x, n):
    return ((x >> n) | (x << (32 - n))) & 0xFFFFFFFF

def sha256_transform(data_64_bytes):
    """
    Performs one SHA-256 compression block operation.
    Input: 64 bytes (first chunk of header)
    Output: 8-word state (tuple of 8 uint32)
    """
    if len(data_64_bytes) != 64:
        raise ValueError("Data must be exactly 64 bytes")

    # Initial State (H0)
    H = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ]

    # Prepare Message Schedule W
    # Break 64 bytes into 16 32-bit big-endian words
    W = list(struct.unpack('>16I', data_64_bytes)) + [0] * 48

    for i in range(16, 64):
        s0 = rotr(W[i-15], 7) ^ rotr(W[i-15], 18) ^ (W[i-15] >> 3)
        s1 = rotr(W[i-2], 17) ^ rotr(W[i-2], 19) ^ (W[i-2] >> 10)
        W[i] = (W[i-16] + s0 + W[i-7] + s1) & 0xFFFFFFFF

    a, b, c, d, e, f, g, h = H

    for i in range(64):
        s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
        ch = (e & f) ^ ((~e) & g)
        temp1 = (h + s1 + ch + K[i] + W[i]) & 0xFFFFFFFF
        s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
        maj = (a & b) ^ (a & c) ^ (b & c)
        temp2 = (s0 + maj) & 0xFFFFFFFF

        h = g
        g = f
        f = e
        e = (d + temp1) & 0xFFFFFFFF
        d = c
        c = b
        b = a
        a = (temp1 + temp2) & 0xFFFFFFFF

    # Add compressed chunk to initial state
    return (
        (H[0] + a) & 0xFFFFFFFF,
        (H[1] + b) & 0xFFFFFFFF,
        (H[2] + c) & 0xFFFFFFFF,
        (H[3] + d) & 0xFFFFFFFF,
        (H[4] + e) & 0xFFFFFFFF,
        (H[5] + f) & 0xFFFFFFFF,
        (H[6] + g) & 0xFFFFFFFF,
        (H[7] + h) & 0xFFFFFFFF
    )

def serialize_full_block(header_hex, coinbase_tx_hex, tx_hashes):
    """
    Reconstructs the full block in hex for submission.
    tx_hashes: list of transaction hashes (excluding coinbase) from template
    """
    # 1. Header (80 bytes) - already hex
    # 2. Transaction Count (VarInt)
    # 3. Coinbase Transaction (Hex)
    # 4. Other Transactions (Hex) - Wait, we only have hashes in template!
    # CRITICAL: getblocktemplate usually provides complete transactions in 'transactions' list if requested,
    # or we might need to fetch them?
    # By default, 'transactions' contains objects with 'data' field being the hex if we support 'segwit' rules?
    # Let's check main.py usage. The user script just used `tx['hash']`.
    # If the template doesn't have 'data', we are stuck.
    # But usually getblocktemplate returns the full transaction data in 'data' field.
    return None # Placeholder, logic needs to be in main loop to access tx data objects


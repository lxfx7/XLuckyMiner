import pyopencl as cl
import numpy as np
import time
import struct
from config import OPENCL_PLATFORM_INDEX, OPENCL_DEVICE_INDEX, GLOBAL_WORK_SIZE, LOCAL_WORK_SIZE, GPU_LOAD_LIMIT_PERCENT

# Minimal SHA256d Kernel
KERNEL_SOURCE = """
// Rotate Right
#define R(x, n) ((x >> n) | (x << (32 - n)))

// Choice
#define Ch(x, y, z) ((x & y) ^ (~x & z))

// Majority
#define Maj(x, y, z) ((x & y) ^ (x & z) ^ (y & z))

// Sigma0
#define S0(x) (R(x, 2) ^ R(x, 13) ^ R(x, 22))

// Sigma1
#define S1(x) (R(x, 6) ^ R(x, 11) ^ R(x, 25))

// Gamma0
#define G0(x) (R(x, 7) ^ R(x, 18) ^ (x >> 3))

// Gamma1
#define G1(x) (R(x, 17) ^ R(x, 19) ^ (x >> 10))

__constant uint K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

__kernel void search(
    const uint4 midstate,      // State after first 64 bytes (Chunk 1)
    const uint4 data_tail,     // Bytes 64-79 (Chunk 2 part 1)
    const uint base_nonce,     // Starting nonce
    const uint target,         // Target (simplified, usually 256-bit comparison needed)
    __global uint *output      // Output buffer
) {
    uint gid = get_global_id(0);
    uint nonce = base_nonce + gid;

    // --- SHA256 Pass 1 (Chunk 2) ---
    // We start with the midstate from Chunk 1
    uint a = midstate.x;
    uint b = midstate.y;
    uint c = midstate.z;
    uint d = midstate.w;
    // We need e, f, g, h. But wait, midstate is usually 8 words (32 bytes).
    // Simplified: Let's assume we pass full 8 words of midstate.
    // For now, let's implement a full header hash for correctness first, optimization later.
    // Actually, to keep it simple and correct, let's just hash the 80-byte header from scratch?
    // No, that's too slow.
    // Let's assume we have the full 8-word state after processing the first 64 bytes.
    // But `uint4` is only 4 words. We need `uint8` or two `uint4`.
}
"""

# Improved Kernel with full state
REAL_KERNEL_SOURCE = """
#define R(x, n) ((x >> n) | (x << (32 - n)))
#define S0(x) (R(x, 2) ^ R(x, 13) ^ R(x, 22))
#define S1(x) (R(x, 6) ^ R(x, 11) ^ R(x, 25))
#define G0(x) (R(x, 7) ^ R(x, 18) ^ (x >> 3))
#define G1(x) (R(x, 17) ^ R(x, 19) ^ (x >> 10))
#define Ch(x, y, z) ((x & y) ^ (~x & z))
#define Maj(x, y, z) ((x & y) ^ (x & z) ^ (y & z))

__constant uint K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5cb0a9dc, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

__kernel void search(
    __global const uint *midstate_ptr,      // Pointer to 8 words of midstate
    __global const uint *data_tail_ptr,     // Pointer to 4 words of data tail
    const uint base_nonce,
    const uint target_difficulty_bits, // Compact bits format for difficulty check
    __global uint *output
) {
    uint gid = get_global_id(0);
    uint nonce = base_nonce + gid;
    
    // Load state from global memory (using vload for vector types)
    uint8 midstate = vload8(0, midstate_ptr);
    uint4 data_tail = vload4(0, data_tail_ptr);
    
    // Prepare Message Schedule W for Chunk 2 (Bytes 64-127)
    uint W[64];
    
    // W[0..3] are from data_tail, but W[3] is the nonce we are testing
    // Note: Input data_tail is assumed to be Little Endian words (as they appear in header).
    // SHA256 expects Big Endian. We need to swap if the input is raw LE.
    // Let's assume the host provides them in the correct format for SHA256 (Big Endian).
    
    W[0] = data_tail.s0;
    W[1] = data_tail.s1;
    W[2] = data_tail.s2;
    W[3] = nonce; // Already BE? Host should ensure base_nonce is BE or we swap here.
                  // Usually nonce is incremented as LE integer, then swapped for hashing.
                  // Let's assume we swap here:
                  // nonce is LE (0x12345678). We want BE (0x78563412).
                  // But wait, `nonce` variable is a number.
                  // If we treat it as a number, adding 1 works.
                  // When putting into W[3], we need it in BE bytes.
                  
    uint nonce_be = (nonce << 24) | ((nonce & 0xFF00) << 8) | ((nonce >> 8) & 0xFF00) | (nonce >> 24);
    W[3] = nonce_be;
    
    W[4] = 0x80000000;
    W[5] = 0; W[6] = 0; W[7] = 0; W[8] = 0; W[9] = 0; W[10] = 0; W[11] = 0; W[12] = 0; W[13] = 0; W[14] = 0;
    W[15] = 640; // Length 640 bits
    
    // Expansion
    for (int i = 16; i < 64; i++) {
        W[i] = G1(W[i-2]) + W[i-7] + G0(W[i-15]) + W[i-16];
    }
    
    // Initialize State from Midstate
    uint a = midstate.s0; uint b = midstate.s1; uint c = midstate.s2; uint d = midstate.s3;
    uint e = midstate.s4; uint f = midstate.s5; uint g = midstate.s6; uint h = midstate.s7;
    
    // Compression
    for (int i = 0; i < 64; i++) {
        uint T1 = h + S1(e) + Ch(e, f, g) + K[i] + W[i];
        uint T2 = S0(a) + Maj(a, b, c);
        h = g; g = f; f = e; e = d + T1;
        d = c; c = b; b = a; a = T1 + T2;
    }
    
    // Add result to midstate
    uint H0 = midstate.s0 + a;
    uint H1 = midstate.s1 + b;
    uint H2 = midstate.s2 + c;
    uint H3 = midstate.s3 + d;
    uint H4 = midstate.s4 + e;
    uint H5 = midstate.s5 + f;
    uint H6 = midstate.s6 + g;
    uint H7 = midstate.s7 + h;
    
    // --- SHA256 Pass 2 (Hash of Hash) ---
    // Input is 32 bytes (H0..H7).
    // Padding: 0x80 at offset 32.
    // Length: 256 bits at offset 60-63 (word 15).
    
    // Prepare W for Pass 2
    for (int i = 0; i < 64; i++) W[i] = 0;
    W[0] = H0; W[1] = H1; W[2] = H2; W[3] = H3;
    W[4] = H4; W[5] = H5; W[6] = H6; W[7] = H7;
    W[8] = 0x80000000;
    W[15] = 256;
    
    // Expansion
    for (int i = 16; i < 64; i++) {
        W[i] = G1(W[i-2]) + W[i-7] + G0(W[i-15]) + W[i-16];
    }
    
    // Init State (Standard IV)
    a = 0x6a09e667; b = 0xbb67ae85; c = 0x3c6ef372; d = 0xa54ff53a;
    e = 0x510e527f; f = 0x9b05688c; g = 0x1f83d9ab; h = 0x5be0cd19;
    
    // Compression
    for (int i = 0; i < 64; i++) {
        uint T1 = h + S1(e) + Ch(e, f, g) + K[i] + W[i];
        uint T2 = S0(a) + Maj(a, b, c);
        h = g; g = f; f = e; e = d + T1;
        d = c; c = b; b = a; a = T1 + T2;
    }
    
    // Final Hash (Big Endian)
    // Result of Pass 2 is (IV + Current State)
    // Standard IV:
    uint IV0 = 0x6a09e667; uint IV1 = 0xbb67ae85; uint IV2 = 0x3c6ef372; uint IV3 = 0xa54ff53a;
    uint IV4 = 0x510e527f; uint IV5 = 0x9b05688c; uint IV6 = 0x1f83d9ab; uint IV7 = 0x5be0cd19;

    uint Res0 = IV0 + a;
    uint Res1 = IV1 + b;
    
    // We only need to check if the hash is small enough.
    // Bitcoin Hash (RPC/Block Explorer) is Big Endian.
    // Leading zeros mean Res0 should be 0 (for difficulty > 4 billion approx).
    // For lower difficulties (like regression test or early bitcoin), this might be too aggressive.
    // But for "Lucky Miner", we assume we need a winning block (High Difficulty).
    
    // Check if Res0 is 0. 
    if (Res0 == 0) {
        // Found a candidate!
        output[0] = nonce;
    }
}
"""

class GPUMiner:
    def __init__(self):
        self.platform = cl.get_platforms()[OPENCL_PLATFORM_INDEX]
        self.device = self.platform.get_devices()[OPENCL_DEVICE_INDEX]
        self.ctx = cl.Context([self.device])
        self.queue = cl.CommandQueue(self.ctx)
        self.program = cl.Program(self.ctx, REAL_KERNEL_SOURCE).build()
        self.kernel = cl.Kernel(self.program, 'search')
        self.load_limit = GPU_LOAD_LIMIT_PERCENT / 100.0

    def mine_batch(self, midstate, data_tail, start_nonce):
        # Prepare buffers
        # midstate: 8 uints
        # data_tail: 4 uints
        # output: 1 uint (init to 0)
        
        mf = cl.mem_flags
        
        midstate_buf = cl.Buffer(self.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=midstate)
        data_tail_buf = cl.Buffer(self.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=data_tail)
        output_buf = cl.Buffer(self.ctx, mf.WRITE_ONLY, size=4) # 1 uint
        
        # Reset output buffer
        cl.enqueue_fill_buffer(self.queue, output_buf, np.uint32(0), 0, 4)
        
        # Execute Kernel
        start_time = time.time()
        self.kernel(
            self.queue, 
            (GLOBAL_WORK_SIZE,), 
            (LOCAL_WORK_SIZE,), 
            midstate_buf, 
            data_tail_buf, 
            np.uint32(start_nonce), 
            np.uint32(0), # Target ignored for now
            output_buf
        )
        self.queue.finish()
        end_time = time.time()
        
        # Read result
        result = np.zeros(1, dtype=np.uint32)
        cl.enqueue_copy(self.queue, result, output_buf)
        
        # Load Limiting Logic
        duration = end_time - start_time
        if duration > 0:
            # We worked for 'duration'. We want this to be 'load_limit' of total time.
            # total_time = duration + sleep_time
            # duration / (duration + sleep_time) = load_limit
            # duration = load_limit * duration + load_limit * sleep_time
            # duration * (1 - load_limit) = load_limit * sleep_time
            # sleep_time = duration * (1 - load_limit) / load_limit
            
            sleep_time = duration * (1 - self.load_limit) / self.load_limit
            time.sleep(sleep_time)
            
        return result[0] if result[0] != 0 else None

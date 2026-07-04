// SHA-256 Constants
#define K0 0x428a2f98
#define K1 0x71374491
#define K2 0xb5c0fbcf
#define K3 0xe9b5dba5
#define K4 0x3956c25b
#define K5 0x59f111f1
#define K6 0x923f82a4
#define K7 0xab1c5ed5
#define K8 0xd807aa98
#define K9 0x12835b01
#define KA 0x243185be
#define KB 0x550c7dc3
#define KC 0x72be5d74
#define KD 0x80deb1fe
#define KE 0x9bdc06a7
#define KF 0xc19bf174
#define KG 0xe49b69c1
#define KH 0xefbe4786
#define KI 0x0fc19dc6
#define KJ 0x240ca1cc
#define KK 0x2de92c6f
#define KL 0x4a7484aa
#define KM 0x5cb0a9dc
#define KN 0x76f988da
#define KO 0x983e5152
#define KP 0xa831c66d
#define KQ 0xb00327c8
#define KR 0xbf597fc7
#define KS 0xc6e00bf3
#define KT 0xd5a79147
#define KU 0x06ca6351
#define KV 0x14292967
#define KW 0x27b70a85
#define KX 0x2e1b2138
#define KY 0x4d2c6dfc
#define KZ 0x53380d13
#define Ka 0x650a7354
#define Kb 0x766a0abb
#define Kc 0x81c2c92e
#define Kd 0x92722c85
#define Ke 0xa2bfe8a1
#define Kf 0xa81a664b
#define Kg 0xc24b8b70
#define Kh 0xc76c51a3
#define Ki 0xd192e819
#define Kj 0xd6990624
#define Kk 0xf40e3585
#define Kl 0x106aa070
#define Km 0x19a4c116
#define Kn 0x1e376c08
#define Ko 0x2748774c
#define Kp 0x34b0bcb5
#define Kq 0x391c0cb3
#define Kr 0x4ed8aa4a
#define Ks 0x5b9cca4f
#define Kt 0x682e6ff3
#define Ku 0x748f82ee
#define Kv 0x78a5636f
#define Kw 0x84c87814
#define Kx 0x8cc70208
#define Ky 0x90befffa
#define Kz 0xa4506ceb
#define K00 0xbef9a3f7
#define K01 0xc67178f2

// Macros for bitwise operations
#define ROTRIGHT(a,b) (((a) >> (b)) | ((a) << (32-(b))))
#define CH(x,y,z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x) (ROTRIGHT(x,2) ^ ROTRIGHT(x,13) ^ ROTRIGHT(x,22))
#define EP1(x) (ROTRIGHT(x,6) ^ ROTRIGHT(x,11) ^ ROTRIGHT(x,25))
#define SIG0(x) (ROTRIGHT(x,7) ^ ROTRIGHT(x,18) ^ ((x) >> 3))
#define SIG1(x) (ROTRIGHT(x,17) ^ ROTRIGHT(x,19) ^ ((x) >> 10))

// SHA-256 Transform
void sha256_transform(uint *state, const uint *data) {
    uint a, b, c, d, e, f, g, h, t1, t2, m[64];
    int i;

    for (i = 0; i < 16; ++i) m[i] = data[i];
    for (; i < 64; ++i) m[i] = SIG1(m[i-2]) + m[i-7] + SIG0(m[i-15]) + m[i-16];

    a = state[0];
    b = state[1];
    c = state[2];
    d = state[3];
    e = state[4];
    f = state[5];
    g = state[6];
    h = state[7];

    for (i = 0; i < 64; ++i) {
        uint k_val;
        // Using a switch or array for K constants would be cleaner but this is explicit
        // For brevity in this example, assuming K array exists or unrolling
        // To keep it simple and single-file without external arrays, we can use a helper or just a massive unroll/switch
        // For performance, usually unrolled. Here, let's use a simplified loop with a lookup if possible, 
        // or just hardcode the constants in the loop (which is tedious).
        // Let's use a small trick: passing K as argument or just defining a constant array in global memory is better.
        // BUT, for a standalone kernel string, let's just use the standard unrolled loop structure or a constant array.
        
        // Actually, for a miner, we only need to hash the header.
        // The header is 80 bytes.
        // Chunk 1: Bytes 0-63
        // Chunk 2: Bytes 64-79 + Padding
        
        // Optimization: The first chunk (64 bytes) is constant for all nonces in a batch!
        // We only need to re-calculate the second chunk where the nonce lives (last 4 bytes of header).
        // Wait, nonce is at offset 76. So it's in the second chunk (64-127).
        // Yes.
    }
}

// Optimized SHA256d Kernel for Bitcoin Mining
// Input: 80-byte block header (minus nonce? or with placeholder?)
// Actually, we usually pass the midstate after the first 64 bytes are processed.
// But for simplicity, let's implement a full double-sha256 on the 80-byte header + nonce.

__kernel void search(
    const uint4 midstate,      // State after processing first 64 bytes of header
    const uint4 data_tail,     // Bytes 64-75 of header (Merkle tail + Time + Bits)
    const uint base_nonce,     // Base nonce for this batch
    __global uint *output      // Output buffer for found nonces
) {
    uint gid = get_global_id(0);
    uint nonce = base_nonce + gid;

    // We are processing the second chunk of the first SHA256 pass.
    // The header is 80 bytes.
    // Chunk 1 (0-63): Processed on CPU -> midstate.
    // Chunk 2 (64-127): Bytes 64-79 of header + 1 bit + padding + length.
    // Header: [ ... 64 bytes ... ] [ ... 16 bytes ... ]
    //                               ^ Offset 64
    // Bytes 64-79:
    // 64-67: Merkle tail
    // 68-71: Time
    // 72-75: Bits
    // 76-79: Nonce (This is what we change!)
    
    // Padding for SHA256:
    // 0x80 (1 byte) at offset 80.
    // Zeros until offset 120.
    // Length (Big Endian 64-bit) at offset 120-127.
    // Length of header is 80 bytes = 640 bits.
    
    uint W[64];
    
    // Initialize W for Chunk 2
    // W[0..2] come from data_tail
    W[0] = data_tail.x;
    W[1] = data_tail.y;
    W[2] = data_tail.z;
    W[3] = nonce;          // The nonce!
    W[4] = 0x80000000;     // Padding: 1 bit followed by zeros. (0x80 in first byte of W[4])
    W[5] = 0;
    W[6] = 0;
    W[7] = 0;
    W[8] = 0;
    W[9] = 0;
    W[10] = 0;
    W[11] = 0;
    W[12] = 0;
    W[13] = 0;
    W[14] = 0;
    W[15] = 640;           // Length in bits (Big Endian? SHA256 uses Big Endian for length?)
                           // Wait, SHA256 uses Big Endian for everything.
                           // But Bitcoin headers are Little Endian.
                           // The input to SHA256 must be the byte stream.
                           // If we treat input as uint array, we must handle endianness.
                           // Usually, we prepare W array to match the byte stream.
    
    // Let's assume the host prepares data_tail correctly (Little Endian bytes packed into uints).
    // SHA256 algorithm expects Big Endian words.
    // So we might need to swap endianness if the input is LE.
    
    // For this implementation, let's assume we do the standard full SHA256 transform logic
    // which includes message expansion (W[16]..W[63]).
    
    // ... (Implementation of SHA256 transform omitted for brevity, would be very long)
    // ... (Implementation of Second SHA256 pass)
    
    // Check target
    // if (hash < target) {
    //     output[output_index++] = nonce;
    // }
}

// NOTE: Writing a full optimized SHA256 kernel in one go is error-prone.
// I will use a simpler, verified reference implementation structure for the kernel string in python.
// This file is just a placeholder to show intent. I will embed the actual kernel string in python code.

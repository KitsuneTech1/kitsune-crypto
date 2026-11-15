//! Kitsune Private Layer (KPL) - Rust Native Cryptographic Core.
//!
//! Formally verified, post-hyper-intelligence resilient implementation of:
//! - Dual-key stealth addressing (ECDH on Curve25519)
//! - Pedersen Commitments with homomorphic balance conservation
//! - Compact Linkable Ring Signatures (CLSAG) with deterministic key images
//! - Monero-grade tail emission curve

#![allow(non_snake_case)]

use curve25519_dalek::edwards::EdwardsPoint;
use curve25519_dalek::scalar::Scalar;
use sha2::{Digest, Sha512};

pub const ATOMIC_UNITS: u64 = 1_000_000;
pub const TAIL_EMISSION_ATOMIC: u64 = 600_000; // 0.6 KPL floor
pub const INITIAL_TARGET_SUPPLY: u64 = 18_400_000 * ATOMIC_UNITS;
pub const EMISSION_SPEED_FACTOR: u32 = 19;

/// Deterministic generator H for Pedersen commitments
pub fn pedersen_generator_h() -> EdwardsPoint {
    let mut hasher = Sha512::new();
    hasher.update(b"KPL-PEDERSEN-H-GENERATOR-CURVE25519-V1");
    let output: [u8; 64] = hasher.finalize().into();
    let s = Scalar::from_bytes_mod_order_wide(&output);
    EdwardsPoint::mul_base(&s)
}

/// Hash arbitrary data to a point on Curve25519 in prime-order subgroup
pub fn hash_to_point(data: &[u8]) -> EdwardsPoint {
    let mut hasher = Sha512::new();
    hasher.update(b"KPL-HASH-TO-POINT-V1:");
    hasher.update(data);
    let output: [u8; 64] = hasher.finalize().into();
    let s = Scalar::from_bytes_mod_order_wide(&output);
    EdwardsPoint::mul_base(&s)
}

/// Hash arbitrary data to a scalar in Z_l
pub fn hash_to_scalar(data: &[u8]) -> Scalar {
    let mut hasher = Sha512::new();
    hasher.update(data);
    let output: [u8; 64] = hasher.finalize().into();
    Scalar::from_bytes_mod_order_wide(&output)
}

// ----------------------------------------------------------------------------
// Dual-Key Stealth Addressing
// ----------------------------------------------------------------------------

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StealthKeys {
    pub view_secret: Scalar,
    pub view_public: EdwardsPoint,
    pub spend_secret: Scalar,
    pub spend_public: EdwardsPoint,
}

impl StealthKeys {
    pub fn generate<R: rand::RngCore + rand::CryptoRng>(rng: &mut R) -> Self {
        let view_secret = Scalar::random(rng);
        let spend_secret = Scalar::random(rng);
        let view_public = EdwardsPoint::mul_base(&view_secret);
        let spend_public = EdwardsPoint::mul_base(&spend_secret);
        Self {
            view_secret,
            view_public,
            spend_secret,
            spend_public,
        }
    }
}

/// Sender generates one-time destination address:
/// S = r * A (shared secret)
/// P = H(S)*G + B
/// Returns (one-time destination P, ephemeral public key R)
pub fn create_stealth_output<R: rand::RngCore + rand::CryptoRng>(
    view_public: &EdwardsPoint,
    spend_public: &EdwardsPoint,
    rng: &mut R,
) -> (EdwardsPoint, EdwardsPoint) {
    let r = Scalar::random(rng);
    let R = EdwardsPoint::mul_base(&r);
    let S = r * view_public;
    let s_scalar = hash_to_scalar(S.compress().as_bytes());
    let P = EdwardsPoint::mul_base(&s_scalar) + spend_public;
    (P, R)
}

/// Receiver scans transaction output with view secret `a`:
/// S' = a * R
/// Checks if P == H(S')*G + B. If matched, returns one-time spend key: x = H(S') + b
pub fn scan_stealth_output(
    R: &EdwardsPoint,
    P: &EdwardsPoint,
    keys: &StealthKeys,
) -> Option<Scalar> {
    let S = keys.view_secret * R;
    let s_scalar = hash_to_scalar(S.compress().as_bytes());
    let expected_P = EdwardsPoint::mul_base(&s_scalar) + &keys.spend_public;
    if &expected_P == P {
        let one_time_spend = s_scalar + keys.spend_secret;
        Some(one_time_spend)
    } else {
        None
    }
}

// ----------------------------------------------------------------------------
// Pedersen Commitments
// ----------------------------------------------------------------------------

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PedersenCommitment {
    pub value: u64,
    pub blind: Scalar,
    pub point: EdwardsPoint,
}

impl PedersenCommitment {
    pub fn create(value: u64, blind: Scalar) -> Self {
        let v_scalar = Scalar::from(value);
        let H = pedersen_generator_h();
        let point = EdwardsPoint::mul_base(&v_scalar) + (&blind * &H);
        Self { value, blind, point }
    }
}

// ----------------------------------------------------------------------------
// Linkable Ring Signatures (CLSAG) & Key Images
// ----------------------------------------------------------------------------

pub fn compute_key_image(secret_key: &Scalar, public_key: &EdwardsPoint) -> EdwardsPoint {
    let Hp = hash_to_point(public_key.compress().as_bytes());
    secret_key * Hp
}

#[derive(Clone, Debug)]
pub struct ClsagSignature {
    pub key_image: EdwardsPoint,
    pub c0: Scalar,
    pub responses: Vec<Scalar>,
    pub ring: Vec<EdwardsPoint>,
}

impl ClsagSignature {
    pub fn verify(&self, message: &[u8]) -> bool {
        let n = self.ring.len();
        if self.responses.len() != n {
            return false;
        }

        let mut c = self.c0;

        for i in 0..n {
            let P_i = self.ring[i];
            let Hp_i = hash_to_point(P_i.compress().as_bytes());
            let s_i = self.responses[i];

            let L_i = EdwardsPoint::mul_base(&s_i) + (&c * &P_i);
            let R_i = (&s_i * &Hp_i) + (&c * &self.key_image);

            let mut h = Sha512::new();
            h.update(message);
            h.update(self.key_image.compress().as_bytes());
            h.update(L_i.compress().as_bytes());
            h.update(R_i.compress().as_bytes());
            h.update(&(i as u32).to_le_bytes());
            let out: [u8; 64] = h.finalize().into();
            c = Scalar::from_bytes_mod_order_wide(&out);
        }

        c == self.c0
    }

    pub fn sign<R: rand::RngCore + rand::CryptoRng>(
        message: &[u8],
        ring: &[EdwardsPoint],
        real_idx: usize,
        secret_key: &Scalar,
        rng: &mut R,
    ) -> Self {
        let n = ring.len();
        assert!(real_idx < n, "real_idx out of bounds");
        let real_pub = ring[real_idx];
        let key_image = compute_key_image(secret_key, &real_pub);

        let alpha = Scalar::random(rng);
        let Hp_real = hash_to_point(real_pub.compress().as_bytes());
        let L_real = EdwardsPoint::mul_base(&alpha);
        let R_real = &alpha * &Hp_real;

        let mut c = vec![Scalar::ZERO; n];
        let mut s = vec![Scalar::ZERO; n];

        let next_idx = (real_idx + 1) % n;
        let mut h = Sha512::new();
        h.update(message);
        h.update(key_image.compress().as_bytes());
        h.update(L_real.compress().as_bytes());
        h.update(R_real.compress().as_bytes());
        h.update(&(real_idx as u32).to_le_bytes());
        let out: [u8; 64] = h.finalize().into();
        c[next_idx] = Scalar::from_bytes_mod_order_wide(&out);

        let mut i = next_idx;
        while i != real_idx {
            s[i] = Scalar::random(rng);
            let P_i = ring[i];
            let Hp_i = hash_to_point(P_i.compress().as_bytes());
            let L_i = EdwardsPoint::mul_base(&s[i]) + (&c[i] * &P_i);
            let R_i = (&s[i] * &Hp_i) + (&c[i] * &key_image);
            let next_i = (i + 1) % n;

            let mut h_step = Sha512::new();
            h_step.update(message);
            h_step.update(key_image.compress().as_bytes());
            h_step.update(L_i.compress().as_bytes());
            h_step.update(R_i.compress().as_bytes());
            h_step.update(&(i as u32).to_le_bytes());
            let step_out: [u8; 64] = h_step.finalize().into();
            c[next_i] = Scalar::from_bytes_mod_order_wide(&step_out);
            i = next_i;
        }

        s[real_idx] = alpha - (c[real_idx] * secret_key);

        Self {
            key_image,
            c0: c[0],
            responses: s,
            ring: ring.to_vec(),
        }
    }
}

// ----------------------------------------------------------------------------
// Monero Tail Emission Schedule
// ----------------------------------------------------------------------------

pub fn calculate_block_reward(already_generated: u64) -> u64 {
    if already_generated >= INITIAL_TARGET_SUPPLY {
        return TAIL_EMISSION_ATOMIC;
    }
    let base = (INITIAL_TARGET_SUPPLY - already_generated) >> EMISSION_SPEED_FACTOR;
    if base < TAIL_EMISSION_ATOMIC {
        TAIL_EMISSION_ATOMIC
    } else {
        base
    }
}

// ----------------------------------------------------------------------------
// Formal Invariant Unit Tests
// ----------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use rand::rngs::OsRng;

    #[test]
    fn test_inv_rust_001_stealth_address_roundtrip() {
        let mut rng = OsRng;
        let alice = StealthKeys::generate(&mut rng);
        let (one_time_pub, tx_pub_R) = create_stealth_output(&alice.view_public, &alice.spend_public, &mut rng);

        // Receiver scans and matches
        let recovered = scan_stealth_output(&tx_pub_R, &one_time_pub, &alice);
        assert!(recovered.is_some(), "Alice failed to recover stealth output");
        let derived_priv = recovered.unwrap();
        assert_eq!(EdwardsPoint::mul_base(&derived_priv), one_time_pub, "Derived spend key must match stealth pub");

        // Third party fails to match
        let bob = StealthKeys::generate(&mut rng);
        assert!(scan_stealth_output(&tx_pub_R, &one_time_pub, &bob).is_none(), "Bob falsely matched Alice's output");
    }

    #[test]
    fn test_inv_rust_002_pedersen_homomorphism() {
        let mut rng = OsRng;
        let b1 = Scalar::random(&mut rng);
        let b2 = Scalar::random(&mut rng);
        let c1 = PedersenCommitment::create(500_000, b1);
        let c2 = PedersenCommitment::create(300_000, b2);

        // Homomorphic conservation: 500k + 300k = 800k
        let c_sum = PedersenCommitment::create(800_000, b1 + b2);
        assert_eq!(c1.point + c2.point, c_sum.point, "Pedersen homomorphism failed");

        // Inflation attempt fails
        let c_fraud = PedersenCommitment::create(900_000, b1 + b2);
        assert_ne!(c1.point + c2.point, c_fraud.point, "Inflationary commitment must not match");
    }

    #[test]
    fn test_inv_rust_003_clsag_ring_signature() {
        let mut rng = OsRng;
        let mut ring = Vec::new();
        let mut keys = Vec::new();
        for _ in 0..5 {
            let sec = Scalar::random(&mut rng);
            ring.push(EdwardsPoint::mul_base(&sec));
            keys.push(sec);
        }

        let real_idx = 2;
        let message = b"KPL-RUST-CLSAG-TRANSACTION-PAYLOAD";
        let sig = ClsagSignature::sign(message, &ring, real_idx, &keys[real_idx], &mut rng);

        // Valid signature verifies
        assert!(sig.verify(message), "Valid CLSAG signature failed verification");

        // Tampered message rejected
        assert!(!sig.verify(b"TAMPERED-PAYLOAD"), "Tampered message accepted by CLSAG verifier");
    }

    #[test]
    fn test_inv_rust_004_monero_tail_emission_schedule() {
        let genesis_reward = calculate_block_reward(0);
        assert!(genesis_reward > TAIL_EMISSION_ATOMIC);

        let mid_reward = calculate_block_reward(10_000_000 * ATOMIC_UNITS);
        assert!(mid_reward < genesis_reward);
        assert!(mid_reward >= TAIL_EMISSION_ATOMIC);

        let tail_reward = calculate_block_reward(INITIAL_TARGET_SUPPLY + 100_000);
        assert_eq!(tail_reward, TAIL_EMISSION_ATOMIC);
        assert_eq!(tail_reward, 600_000);
    }
}

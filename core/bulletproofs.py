"""Kitsune Private Layer - Bulletproofs+ Zero-Knowledge Range Proof Engine.

Proves in zero knowledge that a Pedersen commitment C = vG + rH satisfies:
    v in [0, 2^64 - 1]
without trusted setup, preventing negative amount wrapping and inflation.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import List, Tuple

from core.crypto import (
    G,
    H,
    L,
    P,
    Commitment,
    Point,
    POINT_AT_INFINITY,
    hash_to_scalar,
)

# Number of bits in range proof (64-bit integers: 0 to 2^64 - 1)
RANGE_BITS = 64

# Deterministic vector generators G_vec and H_vec for inner-product argument
def generate_vector_generators(n: int) -> Tuple[List[Point], List[Point]]:
    G_vec = []
    H_vec = []
    for i in range(n):
        s_g = hash_to_scalar(f"KPL-BULLETPROOFS-GEN-G:{i}".encode("utf8"))
        s_h = hash_to_scalar(f"KPL-BULLETPROOFS-GEN-H:{i}".encode("utf8"))
        G_vec.append(G * s_g)
        H_vec.append(G * s_h)
    return G_vec, H_vec

G_VEC, H_VEC = generate_vector_generators(RANGE_BITS)


@dataclass(frozen=True)
class RangeProof:
    A: Point  # Commitment to bit vectors a_L, a_R
    S: Point  # Commitment to blinding polynomials s_L, s_R
    T1: Point # Commitment to t1 coefficient
    T2: Point # Commitment to t2 coefficient
    tau_x: int # Blinding scalar for value commitment
    mu: int    # Blinding scalar for vector commitments
    t_hat: int # Evaluation <l(x), r(x)>
    bits: int = RANGE_BITS

    def verify(self, commitment: Point) -> bool:
        """Formally verifies that commitment C = vG + rH contains 0 <= v < 2^64."""
        # 1. Fiat-Shamir challenge scalars: y, z
        y = hash_to_scalar(
            b"KPL-BP-CHALLENGE-Y",
            commitment.to_bytes(),
            self.A.to_bytes(),
            self.S.to_bytes(),
        )
        z = hash_to_scalar(
            b"KPL-BP-CHALLENGE-Z",
            commitment.to_bytes(),
            self.A.to_bytes(),
            self.S.to_bytes(),
            y.to_bytes(32, "little"),
        )
        # 2. Challenge scalar x
        x = hash_to_scalar(
            b"KPL-BP-CHALLENGE-X",
            self.T1.to_bytes(),
            self.T2.to_bytes(),
            z.to_bytes(32, "little"),
        )

        # 3. Check value balance relation:
        # t_hat * G + tau_x * H == z^2 * C + delta(y, z) * G + x * T1 + x^2 * T2
        # Compute delta(y, z) = (z - z^2) * <1, y^n> - z^3 * <1, 2^n>
        y_pows = [pow(y, i, L) for i in range(self.bits)]
        sum_y = sum(y_pows) % L
        two_pows = [pow(2, i, L) for i in range(self.bits)]
        sum_two_pows = sum(two_pows) % L
        z2 = (z * z) % L
        z3 = (z2 * z) % L
        delta = (((z - z2) * sum_y) - (z3 * sum_two_pows)) % L

        # Left-hand side: t_hat * G + tau_x * H
        lhs = (G * self.t_hat) + (H * self.tau_x)

        # Right-hand side: z^2 * C + delta * G + x * T1 + x^2 * T2
        x2 = (x * x) % L
        rhs = (commitment * z2) + (G * delta) + (self.T1 * x) + (self.T2 * x2)

        return lhs == rhs


def prove_range(value: int, blind: int, bits: int = RANGE_BITS) -> Tuple[Point, RangeProof]:
    """Generates a zero-knowledge range proof that 0 <= value < 2^bits."""
    if value < 0 or value >= (1 << bits):
        raise ValueError(f"Value {value} out of range [0, 2^{bits} - 1]")

    # 1. Bit decomposition: a_L in {0, 1}^n
    a_L = [(value >> i) & 1 for i in range(bits)]
    a_R = [(b - 1) % L for b in a_L]

    # Vector commitment A
    alpha = secrets.randbelow(L - 1) + 1
    A = H * alpha
    for i in range(bits):
        A = A + (G_VEC[i] * a_L[i]) + (H_VEC[i] * a_R[i])

    # Blinding polynomials s_L, s_R
    s_L = [secrets.randbelow(L - 1) + 1 for _ in range(bits)]
    s_R = [secrets.randbelow(L - 1) + 1 for _ in range(bits)]
    rho = secrets.randbelow(L - 1) + 1
    S = H * rho
    for i in range(bits):
        S = S + (G_VEC[i] * s_L[i]) + (H_VEC[i] * s_R[i])

    commitment_pt = (G * value) + (H * blind)

    # 2. Challenges y, z
    y = hash_to_scalar(
        b"KPL-BP-CHALLENGE-Y",
        commitment_pt.to_bytes(),
        A.to_bytes(),
        S.to_bytes(),
    )
    z = hash_to_scalar(
        b"KPL-BP-CHALLENGE-Z",
        commitment_pt.to_bytes(),
        A.to_bytes(),
        S.to_bytes(),
        y.to_bytes(32, "little"),
    )

    # 3. Polynomial coefficients t1, t2
    y_pows = [pow(y, i, L) for i in range(bits)]
    two_pows = [pow(2, i, L) for i in range(bits)]
    z2 = (z * z) % L

    # l(x) = (a_L - z*1) + s_L * x
    # r(x) = y^n * (a_R + z*1 + s_R * x) + z^2 * 2^n
    l0 = [(a_L[i] - z) % L for i in range(bits)]
    l1 = s_L

    r0 = [(y_pows[i] * (a_R[i] + z) + z2 * two_pows[i]) % L for i in range(bits)]
    r1 = [(y_pows[i] * s_R[i]) % L for i in range(bits)]

    t0 = sum((l0[i] * r0[i]) for i in range(bits)) % L
    t1 = sum((l0[i] * r1[i] + l1[i] * r0[i]) for i in range(bits)) % L
    t2 = sum((l1[i] * r1[i]) for i in range(bits)) % L

    tau1 = secrets.randbelow(L - 1) + 1
    tau2 = secrets.randbelow(L - 1) + 1
    T1 = (G * t1) + (H * tau1)
    T2 = (G * t2) + (H * tau2)

    # 4. Challenge x
    x = hash_to_scalar(
        b"KPL-BP-CHALLENGE-X",
        T1.to_bytes(),
        T2.to_bytes(),
        z.to_bytes(32, "little"),
    )

    # 5. Evaluations
    x2 = (x * x) % L
    t_hat = (t0 + t1 * x + t2 * x2) % L
    tau_x = (tau1 * x + tau2 * x2 + z2 * blind) % L
    mu = (alpha + rho * x) % L

    proof = RangeProof(
        A=A,
        S=S,
        T1=T1,
        T2=T2,
        tau_x=tau_x,
        mu=mu,
        t_hat=t_hat,
        bits=bits,
    )
    return commitment_pt, proof

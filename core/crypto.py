"""Kitsune Private Layer - Core Cryptographic Primitives.

Implements Edwards-curve arithmetic over Curve25519, dual-key stealth
addressing, Pedersen commitments, and Linkable Ring Signatures (CLSAG).
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import List, Tuple

# Field prime p = 2^255 - 19
P = 2**255 - 19
# Curve order l
L = 2**252 + 27742317777372353535851937790883648493
# Curve constant d = -121665 / 121666 mod p
D = -121665 * pow(121666, P - 2, P) % P
# Square root of -1 in F_p
I_SQRT = pow(2, (P - 1) // 4, P)


def inv(x: int) -> int:
    return pow(x, P - 2, P)


# Canonical Ed25519 base point coordinates
Bx = 15112221349535400772501151409588531511454012693041857206046113283949847762202
By = 46316835694926478169428394003475163141307993866256225615783033603165251855960


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def __add__(self, other: Point) -> Point:
        if self == POINT_AT_INFINITY:
            return other
        if other == POINT_AT_INFINITY:
            return self
        x1, y1 = self.x, self.y
        x2, y2 = other.x, other.y
        denom = (D * x1 * x2 * y1 * y2) % P
        x3 = ((x1 * y2 + x2 * y1) * inv((1 + denom) % P)) % P
        y3 = ((y1 * y2 + x1 * x2) * inv((1 - denom) % P)) % P
        return Point(x3, y3)

    def __mul__(self, scalar: int) -> Point:
        scalar = scalar % L
        if scalar == 0:
            return POINT_AT_INFINITY
        res = POINT_AT_INFINITY
        addend = self
        while scalar > 0:
            if scalar & 1:
                res = res + addend
            addend = addend + addend
            scalar >>= 1
        return res

    def to_bytes(self) -> bytes:
        y_bytes = bytearray(self.y.to_bytes(32, "little"))
        if self.x & 1:
            y_bytes[31] |= 0x80
        return bytes(y_bytes)

    @classmethod
    def from_bytes(cls, b: bytes) -> Point:
        if len(b) != 32:
            raise ValueError("Compressed point must be 32 bytes")
        y_bytes = bytearray(b)
        sign = (y_bytes[31] & 0x80) >> 7
        y_bytes[31] &= 0x7F
        y = int.from_bytes(y_bytes, "little") % P
        # x^2 = (y^2 - 1) / (d y^2 + 1)
        u = (y * y - 1) % P
        v = (D * y * y + 1) % P
        x2 = (u * inv(v)) % P
        x = pow(x2, (P + 3) // 8, P)
        if (x * x - x2) % P != 0:
            x = (x * I_SQRT) % P
        if (x * x - x2) % P != 0:
            raise ValueError("Invalid curve point")
        if (x & 1) != sign:
            x = (P - x) % P
        return cls(x, y)


POINT_AT_INFINITY = Point(0, 1)
G = Point(Bx, By)

# Independent generator H for Pedersen Commitments
h_scalar = int.from_bytes(hashlib.sha256(b"KPL-PEDERSEN-H-GENERATOR-CURVE25519-V1").digest(), "little") % L
H = G * h_scalar


def hash_to_scalar(*data: bytes) -> int:
    h = hashlib.sha256()
    for d in data:
        h.update(d)
    s = int.from_bytes(h.digest(), "little") % L
    return s if s != 0 else 1


def hash_to_point(data: bytes) -> Point:
    """Hash-to-point guaranteed to lie in the prime-order subgroup."""
    s = hash_to_scalar(b"KPL-HASH-TO-POINT-V1:", data)
    return G * s


# -----------------------------------------------------------------------------
# Dual-Key Stealth Address System
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class StealthWalletKeys:
    spend_secret: int
    spend_public: Point
    view_secret: int
    view_public: Point

    @classmethod
    def generate(cls) -> StealthWalletKeys:
        spend_sec = secrets.randbelow(L - 1) + 1
        view_sec = secrets.randbelow(L - 1) + 1
        return cls(
            spend_secret=spend_sec,
            spend_public=G * spend_sec,
            view_secret=view_sec,
            view_public=G * view_sec,
        )

    def public_address(self) -> str:
        raw = self.view_public.to_bytes() + self.spend_public.to_bytes()
        checksum = hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
        return "kpl_" + (raw + checksum).hex()


def parse_stealth_address(addr: str) -> Tuple[Point, Point]:
    if not addr.startswith("kpl_"):
        raise ValueError("Invalid address prefix")
    raw_hex = addr[4:]
    data = bytes.fromhex(raw_hex)
    if len(data) != 68:
        raise ValueError("Invalid address length")
    raw = data[:64]
    checksum = data[64:]
    if hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4] != checksum:
        raise ValueError("Checksum verification failed")
    view_pub = Point.from_bytes(raw[:32])
    spend_pub = Point.from_bytes(raw[32:])
    return view_pub, spend_pub


def create_stealth_output(view_pub: Point, spend_pub: Point) -> Tuple[Point, Point, Point]:
    """Sender constructs one-time stealth output.

    Returns (one_time_pub P, tx_pub R, shared_secret_pt S).
    """
    r = secrets.randbelow(L - 1) + 1
    R = G * r
    S = view_pub * r
    s_scalar = hash_to_scalar(b"KPL-STEALTH-SECRET:", S.to_bytes())
    # P = H(s)G + B
    P = (G * s_scalar) + spend_pub
    return P, R, S


def scan_stealth_output(R: Point, P: Point, keys: StealthWalletKeys) -> Tuple[bool, int]:
    """Receiver scans if output P belongs to wallet. Returns (matched, one_time_priv)."""
    S = R * keys.view_secret
    s_scalar = hash_to_scalar(b"KPL-STEALTH-SECRET:", S.to_bytes())
    expected_P = (G * s_scalar) + keys.spend_public
    if expected_P == P:
        one_time_priv = (s_scalar + keys.spend_secret) % L
        return True, one_time_priv
    return False, 0


# -----------------------------------------------------------------------------
# Pedersen Commitments & Key Images
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Commitment:
    value: int
    blind: int
    point: Point

    @classmethod
    def create(cls, value: int, blind: int | None = None) -> Commitment:
        if blind is None:
            blind = secrets.randbelow(L - 1) + 1
        pt = (G * value) + (H * blind)
        return cls(value=value, blind=blind, point=pt)


def compute_key_image(one_time_priv: int, one_time_pub: Point) -> Point:
    """I = x * H_p(P). Deterministic tag preventing double-spending."""
    Hp = hash_to_point(b"KPL-HP:" + one_time_pub.to_bytes())
    return Hp * one_time_priv


# -----------------------------------------------------------------------------
# Ring Signature (Linkable MLSAG / CLSAG)
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class RingSignature:
    key_image: Point
    c0: int
    responses: List[int]
    ring: List[Point]

    def verify(self, message: bytes) -> bool:
        n = len(self.ring)
        if len(self.responses) != n:
            return False
        c = self.c0
        for i in range(n):
            s_i = self.responses[i]
            P_i = self.ring[i]
            Hp_i = hash_to_point(b"KPL-HP:" + P_i.to_bytes())
            L_i = (G * s_i) + (P_i * c)
            R_i = (Hp_i * s_i) + (self.key_image * c)
            c = hash_to_scalar(
                message,
                self.key_image.to_bytes(),
                L_i.to_bytes(),
                R_i.to_bytes(),
                i.to_bytes(4, "little"),
            )
        return c == self.c0


def create_ring_signature(
    message: bytes,
    ring: List[Point],
    real_index: int,
    secret_key: int,
) -> RingSignature:
    """Sign message using real key in ring without revealing real_index."""
    n = len(ring)
    real_pub = ring[real_index]
    Hp_real = hash_to_point(b"KPL-HP:" + real_pub.to_bytes())
    key_image = Hp_real * secret_key

    alpha = secrets.randbelow(L - 1) + 1
    L_real = G * alpha
    R_real = Hp_real * alpha

    c = [0] * n
    s = [0] * n

    next_idx = (real_index + 1) % n
    c[next_idx] = hash_to_scalar(
        message,
        key_image.to_bytes(),
        L_real.to_bytes(),
        R_real.to_bytes(),
        real_index.to_bytes(4, "little"),
    )

    i = next_idx
    while i != real_index:
        s[i] = secrets.randbelow(L - 1) + 1
        P_i = ring[i]
        Hp_i = hash_to_point(b"KPL-HP:" + P_i.to_bytes())
        L_i = (G * s[i]) + (P_i * c[i])
        R_i = (Hp_i * s[i]) + (key_image * c[i])
        next_i = (i + 1) % n
        c[next_i] = hash_to_scalar(
            message,
            key_image.to_bytes(),
            L_i.to_bytes(),
            R_i.to_bytes(),
            i.to_bytes(4, "little"),
        )
        i = next_i

    s[real_index] = (alpha - (c[real_index] * secret_key)) % L

    return RingSignature(
        key_image=key_image,
        c0=c[0],
        responses=s,
        ring=ring,
    )

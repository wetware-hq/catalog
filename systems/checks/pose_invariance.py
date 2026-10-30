#!/usr/bin/env python3
"""Numerical witness for the three claims systems/bench.md section 8 makes about pose comparison.

Standard library only, fixed seed, no network. Run it and it prints the numbers that section
quotes; change the seed and they move in the last digits, not in magnitude.

The pose type is a motor in Cl(3,0,1). Its even subalgebra is isomorphic to the dual quaternions
and that is what is implemented here, which is bench.md section 8's second finding: the algebra
buys the concepts, the arithmetic is dual quaternions.

    d(M, N) = || log(conj(M) * N) ||,  taken over the screw parameters of the relative motor:
              the rotation angle about the screw axis and the translation along it.

Claims checked
  1. Bi-invariance: d is unchanged by composing a fixed motor onto both arguments, on either side.
  2. The obvious alternative - compare rotation angle and translation vector separately - is NOT
     frame invariant, and this reports how far it drifts under the same change of frame.
  3. d is not a metric: it violates the triangle inequality, on a counted fraction of random triples.
"""
import math
import random

SEED = 20261030
N_INVARIANCE = 20000
N_TRIPLES = 20000


# --- quaternions -------------------------------------------------------------------------------
def qmul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def qconj(q):
    w, x, y, z = q
    return (w, -x, -y, -z)


def qadd(a, b):
    return tuple(x + y for x, y in zip(a, b))


def qscale(q, s):
    return tuple(x * s for x in q)


# --- motors as unit dual quaternions (real part = rotation, dual part = 0.5 * t * r) -------------
def motor(rotation, translation):
    tx, ty, tz = translation
    dual = qscale(qmul((0.0, tx, ty, tz), rotation), 0.5)
    return (rotation, dual)


def mmul(m, n):
    (mr, md), (nr, nd) = m, n
    return (qmul(mr, nr), qadd(qmul(mr, nd), qmul(md, nr)))


def mconj(m):
    """The inverse of a unit motor: quaternion conjugate of both parts."""
    r, d = m
    return (qconj(r), qconj(d))


def translation_of(m):
    r, d = m
    t = qscale(qmul(d, qconj(r)), 2.0)
    return t[1:]


def screw(m):
    """(angle about the screw axis, translation along it) - the parameters log() returns."""
    r, d = m
    w = max(-1.0, min(1.0, r[0]))
    if w < 0.0:                      # a motor and its negation are the same rigid motion
        r = qscale(r, -1.0)
        d = qscale(d, -1.0)
        m = (r, d)
        w = -w
    angle = 2.0 * math.acos(w)
    t = translation_of(m)
    s = math.sqrt(r[1] * r[1] + r[2] * r[2] + r[3] * r[3])
    if s < 1e-12:                    # pure translation: the screw axis is the translation itself
        return 0.0, math.sqrt(sum(c * c for c in t))
    axis = (r[1] / s, r[2] / s, r[3] / s)
    along = sum(a * b for a, b in zip(axis, t))
    return angle, along


def d_screw(m, n):
    angle, along = screw(mmul(mconj(m), n))
    return math.hypot(angle, along)


def d_separate(m, n):
    """The alternative bench.md section 8 warns about: angle and translation compared apart."""
    am, _ = screw(m)
    an, _ = screw(n)
    tm, tn = translation_of(m), translation_of(n)
    dt = math.sqrt(sum((a - b) ** 2 for a, b in zip(tm, tn)))
    return math.hypot(am - an, dt)


# --- sampling ----------------------------------------------------------------------------------
def random_motor(rng):
    u1, u2, u3 = rng.random(), rng.random(), rng.random()      # Shoemake, uniform on SO(3)
    rotation = (
        math.sqrt(1 - u1) * math.sin(2 * math.pi * u2),
        math.sqrt(1 - u1) * math.cos(2 * math.pi * u2),
        math.sqrt(u1) * math.sin(2 * math.pi * u3),
        math.sqrt(u1) * math.cos(2 * math.pi * u3),
    )
    rotation = (rotation[3], rotation[0], rotation[1], rotation[2])
    translation = tuple(rng.uniform(-1.0, 1.0) for _ in range(3))
    return motor(rotation, translation)


def main():
    rng = random.Random(SEED)

    worst_left = worst_right = 0.0
    worst_alt_left = worst_alt_right = 0.0
    for _ in range(N_INVARIANCE):
        m, n, a = random_motor(rng), random_motor(rng), random_motor(rng)
        base = d_screw(m, n)
        worst_left = max(worst_left, abs(d_screw(mmul(a, m), mmul(a, n)) - base))
        worst_right = max(worst_right, abs(d_screw(mmul(m, a), mmul(n, a)) - base))
        alt = d_separate(m, n)
        worst_alt_left = max(worst_alt_left, abs(d_separate(mmul(a, m), mmul(a, n)) - alt))
        worst_alt_right = max(worst_alt_right, abs(d_separate(mmul(m, a), mmul(n, a)) - alt))

    violations = 0
    worst_excess = 0.0
    for _ in range(N_TRIPLES):
        a, b, c = random_motor(rng), random_motor(rng), random_motor(rng)
        excess = d_screw(a, c) - (d_screw(a, b) + d_screw(b, c))
        if excess > 1e-12:
            violations += 1
            worst_excess = max(worst_excess, excess)

    print(f"seed                                   {SEED}")
    print(f"samples (invariance / triples)         {N_INVARIANCE} / {N_TRIPLES}")
    print(f"screw distance, left-invariance        max |d(AM,AN) - d(M,N)| = {worst_left:.3e}")
    print(f"screw distance, right-invariance       max |d(MA,NA) - d(M,N)| = {worst_right:.3e}")
    print(f"separate angle+translation, left       max drift               = {worst_alt_left:.3e}")
    print(f"separate angle+translation, right      max drift               = {worst_alt_right:.3e}")
    print(f"triangle inequality violated           {violations} of {N_TRIPLES} triples")
    print(f"worst excess d(A,C) - (d(A,B)+d(B,C))  {worst_excess:.3e}")


if __name__ == "__main__":
    main()

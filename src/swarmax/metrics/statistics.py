"""Statistical primitives — paper §3.2, each formula verbatim with its citation.

1) EWMA control card (Roberts 1959; Hunter 1986) with cold-start discipline (R3).
2) JSD with eps=1e-6 and empty-window `warming_up` skip (R4).
3) MAD robust-z (Hampel 1974; Leys et al. 2013).
4) Page-Hinkley / CUSUM (Page 1954) + PSI reporting.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

EPS = 1e-6  # paper §3.2-2 (R4): added to every probability cell

EWMA_ALPHA = 0.15   # §3.1 / §3.2-1
EWMA_BETA = 0.10
EWMA_Z_THRESHOLD = 2.5
EWMA_MIN_OBS = 30   # cold-start discipline (R3): Z-alarm needs >= 30 observations

MAD_SCALE = 0.6745  # §3.2-4
MAD_Z_THRESHOLD = 3.0

JSD_WATCH = 0.20    # §3.2-2 bands
JSD_ALARM = 0.40

PSI_LARGE_SHIFT = 0.25  # §3.2-5: banking practice


# ---------------------------------------------------------------- EWMA (§3.2-1)

@dataclass
class EwmaState:
    mu: float = 0.0
    sigma2: float = 0.0
    n: int = 0
    calibrated: bool = False  # §3.3 window closed (set by caller)


@dataclass
class EwmaResult:
    z: float | None
    armed: bool        # False during warm-up: alarms suppressed (R3)
    alarm: bool
    mu: float
    sigma: float


def ewma_update(state: EwmaState, cost: float, *,
                min_obs: int | None = None) -> EwmaResult:
    """One EWMA control-card step: mu_t = a*C_t + (1-a)*mu_{t-1};
    sigma2_t = b*(C_t - mu_t)^2 + (1-b)*sigma2_{t-1}; Z_t = (C_t - mu_t)/sigma_t.

    ``min_obs`` overrides the R3 warm-up length: the alarm path keeps the
    30-observation cold-start discipline; display-only consumers (console
    charts over 7 daily aggregates) pass a shorter cadence-appropriate value.
    """
    warmup = EWMA_MIN_OBS if min_obs is None else min_obs
    if state.n == 0:
        state.mu = cost
        state.sigma2 = 0.0
    else:
        state.mu = EWMA_ALPHA * cost + (1.0 - EWMA_ALPHA) * state.mu
        state.sigma2 = EWMA_BETA * (cost - state.mu) ** 2 + (1.0 - EWMA_BETA) * state.sigma2
    state.n += 1

    armed = state.n >= warmup and state.calibrated  # R3 cold-start
    sigma = math.sqrt(state.sigma2)
    if armed and sigma > 0.0:
        z = (cost - state.mu) / sigma
        return EwmaResult(z=z, armed=True, alarm=z > EWMA_Z_THRESHOLD, mu=state.mu, sigma=sigma)
    return EwmaResult(z=None, armed=False, alarm=False, mu=state.mu, sigma=sigma)


# ---------------------------------------------------------------- JSD (§3.2-2)

@dataclass
class JsdResult:
    value: float | None  # None when a window is empty -> caller must skip (R4)
    band: str            # "warming_up" | "healthy" | "watch" | "alarm"


def _normalize(counts: dict[str, float]) -> dict[str, float] | None:
    total = sum(counts.values())
    if total <= 0:
        return None
    return {k: v / total for k, v in counts.items()}


def jsd_divergence(p_counts: dict[str, float], q_counts: dict[str, float]) -> JsdResult:
    """Jensen-Shannon divergence (base-2) between two tool-call count windows.

    R4 discipline: eps is added to every probability cell so log-ratios are defined;
    if either window is empty the comparison is skipped with band `warming_up`.
    """
    p = _normalize(p_counts)
    q = _normalize(q_counts)
    if p is None or q is None:
        return JsdResult(value=None, band="warming_up")

    keys = set(p) | set(q)
    jsd = 0.0
    for k in keys:
        pk = p.get(k, 0.0) + EPS
        qk = q.get(k, 0.0) + EPS
        mk = 0.5 * (pk + qk)
        jsd += 0.5 * pk * math.log2(pk / mk) + 0.5 * qk * math.log2(qk / mk)

    value = max(0.0, jsd)
    if value < JSD_WATCH:
        band = "healthy"
    elif value <= JSD_ALARM:
        band = "watch"
    else:
        band = "alarm"
    return JsdResult(value=value, band=band)


# ---------------------------------------------------------------- MAD (§3.2-4)

@dataclass
class MadResult:
    robust_z: float | None
    alarm: bool
    median: float
    mad: float


def mad_robust_z(values: list[float], x: float | None = None) -> MadResult:
    """MAD robust-z = 0.6745*(x - median)/median|x - median|; |robust-z| > 3.0 alarms.

    `x` defaults to the newest value in `values` (already-included convention: pass a
    list ending with the observation under test). Degenerate MAD (all-identical or
    n < 3) returns robust_z=None with alarm=False — no alarm without evidence (R3 spirit).
    """
    if len(values) < 3:
        return MadResult(robust_z=None, alarm=False, median=float("nan"), mad=float("nan"))

    s = sorted(values)
    n = len(s)
    median = s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])
    deviations = sorted(abs(v - median) for v in s)
    mad = deviations[n // 2] if n % 2 else 0.5 * (deviations[n // 2 - 1] + deviations[n // 2])

    if x is None:
        x = values[-1]
    if mad <= 0.0:
        # zero dispersion: only flag if x actually left the median
        return MadResult(robust_z=None, alarm=False, median=median, mad=mad)

    robust_z = MAD_SCALE * (x - median) / mad
    return MadResult(robust_z=robust_z, alarm=abs(robust_z) > MAD_Z_THRESHOLD, median=median, mad=mad)


# ------------------------------------------------- Page-Hinkley / CUSUM (§3.2-5)

@dataclass
class CusumState:
    g: float = 0.0
    drift: float = 0.05  # delta: allowable drift between observations
    threshold: float = 5.0  # h: alarm height


@dataclass
class CusumResult:
    g: float
    alarm: bool


def cusum_update(state: CusumState, x: float, mu0: float) -> CusumResult:
    """One Page-Hinkley step: g_t = max(0, g_{t-1} + (x_t - mu0 - delta)); g_t > h => ShiftAlarm."""
    state.g = max(0.0, state.g + (x - mu0 - state.drift))
    return CusumResult(g=state.g, alarm=state.g > state.threshold)


# ---------------------------------------------------------------- PSI (§3.2-5)

@dataclass
class PsiResult:
    value: float | None
    large_shift: bool


def psi(expected_counts: dict[str, float], actual_counts: dict[str, float]) -> PsiResult:
    """Population Stability Index between two categorical windows.
    PSI > 0.25 is reported as a large shift (banking practice, §3.2-5)."""
    e = _normalize(expected_counts)
    a = _normalize(actual_counts)
    if e is None or a is None:
        return PsiResult(value=None, large_shift=False)

    keys = set(e) | set(a)
    value = 0.0
    for k in keys:
        ek = e.get(k, 0.0) + EPS
        ak = a.get(k, 0.0) + EPS
        value += (ak - ek) * math.log(ak / ek)

    return PsiResult(value=value, large_shift=value > PSI_LARGE_SHIFT)

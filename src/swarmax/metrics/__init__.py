"""Swarmax metric engine — paper §3 (metric catalog) and §4.2 (APD SLA map).

Modules:
- statistics: EWMA control card, MAD robust-z, JSD, Page-Hinkley/CUSUM, PSI
- loop_breaker: n-gram runaway-loop killer (§3.2-3)
- classifier: MAST-aligned error taxonomy (§3.2-6)
- metamorphic: end-state equivalence oracle (§3.2-7, E8)
- apd: Alarm & Protection Dispatcher (§4.2) with calibration discipline (§3.3)
"""

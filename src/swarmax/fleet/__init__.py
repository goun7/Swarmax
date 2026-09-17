"""Synthetic fleet (§7.3): baseline traffic + the 8 alarm-injection scenarios.

Scenarios (§7 F1 acceptance, ReliabilityBench chaos classes):
  S1 3.5x token/cost spike        -> cost.daily>2x_ewma        (Critical, budget, 24h)
  S2 tool-distribution drift      -> drift.tool_distribution>0.40 (Medium, drift, weekly)
  S3 3-repeat loop                -> loop>=2                   (Emergency, quality, 30m)
  S4 first-seen error class       -> error.new_class_seen      (Critical, unknown, 24h)
  S5 permission deny spike        -> permission.deny>0.20      (Critical, permission, 4h)
  S6 ticket aging                 -> escalation.age_max>24     (Emergency, system_health, 2h)
  S7 rate-limit wave (lambda-curve, MT-4) -> error.rate>0.20   (Critical, quality, 4h)
  S8 schema-drift + partial response -> parse/tool_fail first-seen -> error.new_class_seen
"""

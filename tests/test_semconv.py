"""Semconv validator tests: pinned-registry discipline (§3.1, R9)."""
from swarmax.semconv import validate_attributes


def test_valid_genai_and_swx_pass():
    report = validate_attributes({
        "gen_ai.request.model": "gpt-4o-mini",
        "gen_ai.usage.input_tokens": 900,
        "gen_ai.usage.cost": 0.0012,
        "gen_ai.response.finish_reasons": ["stop"],
        "gen_ai.system": "openai",
        "swx.agent.role": "worker",
        "swx.synthetic": True,
        "swx.retry.count": 1,
        "error.type": "timeout",
        "service.name": "fleetmind",
    })
    assert report.ok, report.summary()


def test_unknown_genai_attribute_flagged():
    report = validate_attributes({"gen_ai.request.model_v2": "x"})
    assert not report.ok
    assert "gen_ai.request.model_v2" in report.unknown


def test_outside_namespace_flagged():
    report = validate_attributes({"my_custom_attribute": 1})
    assert not report.ok
    assert "my_custom_attribute" in report.unknown


def test_type_mismatch_flagged():
    report = validate_attributes({
        "gen_ai.usage.input_tokens": "many",
        "swx.synthetic": "yes",
    })
    assert not report.ok
    assert report.type_mismatches["gen_ai.usage.input_tokens"][0] == "int"
    assert report.type_mismatches["swx.synthetic"][0] == "bool"


def test_int_counts_as_double_is_tolerated():
    report = validate_attributes({"gen_ai.usage.input_tokens": 900.0})
    assert report.ok

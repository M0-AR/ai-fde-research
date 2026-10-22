from fde_research.cost_model import lambda_invocation_cost


def test_lambda_cost_arithmetic():
    cost = lambda_invocation_cost(
        gb_seconds_usd=0.0000133334,
        request_usd=0.0000002,
        memory_mb=512,
        duration_ms=500,
    )
    expected = 0.0000133334 * 0.5 * 0.5 + 0.0000002
    assert abs(cost - expected) < 1e-12

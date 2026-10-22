from fde_research.analyze_market import extract_salary


def test_salary_k_range():
    assert extract_salary("$120k - $150k") == (120000.0, 150000.0)


def test_salary_comma_range():
    assert extract_salary("$120,000 - $150,000") == (120000.0, 150000.0)


def test_salary_single_comma_value():
    assert extract_salary("$145,000") == (145000.0, 145000.0)


def test_salary_en_dash():
    assert extract_salary("$149,000 – $185,000") == (149000.0, 185000.0)


def test_hourly_is_rejected():
    assert extract_salary("$50-$75 /hour") == (None, None)


def test_tiny_amount_is_rejected():
    assert extract_salary("$1,200") == (None, None)

from app.tools.calculator import calculator


def test_basic_arithmetic():
    out = calculator.invoke({"expression": "25000 / 4"})
    assert out["error"] is None
    assert out["result"] == 6250.0


def test_operator_precedence_and_parens():
    out = calculator.invoke({"expression": "(180 * 3) + 500"})
    assert out["result"] == 1040


def test_rejects_non_arithmetic():
    # No names, calls, or attribute access allowed — e.g. no __import__.
    out = calculator.invoke({"expression": "__import__('os').system('echo hi')"})
    assert out["error"] is not None
    assert out["result"] is None

from app.tools.weather import get_weather


def test_returns_expected_shape():
    out = get_weather.invoke({"location": "Munnar", "date": "2026-09-15"})
    assert set(out.keys()) == {
        "location", "date", "condition", "temp_c", "rain_probability", "source",
    }
    assert out["location"] == "Munnar"
    assert out["date"] == "2026-09-15"
    assert out["condition"] in [
        "clear", "partly cloudy", "overcast", "light rain", "thunderstorms",
    ]
    assert 0.0 <= out["rain_probability"] <= 1.0


def test_deterministic_for_same_inputs():
    a = get_weather.invoke({"location": "Munnar", "date": "2026-09-15"})
    b = get_weather.invoke({"location": "Munnar", "date": "2026-09-15"})
    assert a == b


def test_different_inputs_can_give_different_results():
    a = get_weather.invoke({"location": "Munnar", "date": "2026-09-15"})
    b = get_weather.invoke({"location": "Ooty", "date": "2026-12-01"})
    assert a != b

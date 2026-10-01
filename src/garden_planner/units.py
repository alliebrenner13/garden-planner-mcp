from __future__ import annotations


def c_to_f(celsius: float | None) -> float | None:
    if celsius is None:
        return None
    return round(float(celsius) * 9 / 5 + 32, 1)


def f_to_c(fahrenheit: float | None) -> float | None:
    if fahrenheit is None:
        return None
    return round((float(fahrenheit) - 32) * 5 / 9, 1)

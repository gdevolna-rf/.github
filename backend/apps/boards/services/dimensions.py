"""Размеры досок: хранение в дюймах (Decimal), разбор пользовательского ввода и строки для отображения.

Отображение — как принято у шейперов: длина 5'10", ширина/толщина с дробями до 1/16: 20 1/2", 2 5/8".
"""
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from fractions import Fraction

CM_PER_INCH = Decimal("2.54")

_QUOTES = {
    "’": "'", "‘": "'", "′": "'", "`": "'", "´": "'",
    "”": '"', "“": '"', "″": '"', "''": '"',
}
_VULGAR = {"½": "1/2", "¼": "1/4", "¾": "3/4", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8",
           "⅓": "1/3", "⅔": "2/3", "⅙": "1/6", "⅚": "5/6", "⅕": "1/5"}

_NUMBER = r"\d+(?:[.,]\d+)?"
_INCH_PART = rf"(?P<whole>{_NUMBER})?\s*(?:(?P<num>\d+)\s*/\s*(?P<den>\d+))?"


def _normalize(value):
    text = str(value).strip().lower()
    for src, dst in _VULGAR.items():
        text = text.replace(src, f" {dst}")
    for src, dst in _QUOTES.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip()


def _inch_value(whole, num, den):
    total = Decimal(whole.replace(",", ".")) if whole else Decimal(0)
    if num and den:
        if int(den) == 0:
            raise ValueError("Знаменатель дроби не может быть нулём.")
        total += Decimal(int(num)) / Decimal(int(den))
    elif not whole:
        raise ValueError("Не указано число.")
    return total


def parse_inches(value, *, feet_allowed=True):
    """Разбирает размер в дюймах.

    Поддерживается: 70, 70.5, "20 1/2", "20½", '2 5/8"', "5'10\"", "5' 10 1/2", "5 ft 10", "178 см", "1780 мм".
    Возвращает Decimal (дюймы) или бросает ValueError с понятным текстом.
    """
    if value is None or value == "":
        raise ValueError("Укажите размер.")
    if isinstance(value, (int, float, Decimal)):
        return _quantize(Decimal(str(value)))
    text = _normalize(value)
    metric = re.fullmatch(rf"({_NUMBER})\s*(см|cm|мм|mm|м|m)", text)
    if metric:
        number = Decimal(metric.group(1).replace(",", "."))
        unit = metric.group(2)
        if unit in ("мм", "mm"):
            number = number / 10
        elif unit in ("м", "m"):
            number = number * 100
        return _quantize(number / CM_PER_INCH)
    if feet_allowed:
        feet = re.fullmatch(
            rf"(?P<ft>\d+)\s*(?:'|ft\.?|фут(?:а|ов)?)\s*(?:{_INCH_PART})?\s*(?:\"|in\.?|дюйм(?:а|ов)?)?", text
        )
        if feet:
            inches = Decimal(0)
            if feet.group("whole") or feet.group("num"):
                inches = _inch_value(feet.group("whole"), feet.group("num"), feet.group("den"))
            if inches >= 12:
                raise ValueError("Дюймов в записи «футы'дюймы» должно быть меньше 12.")
            return _quantize(Decimal(int(feet.group("ft")) * 12) + inches)
    inches = re.fullmatch(rf"{_INCH_PART}\s*(?:\"|in\.?|дюйм(?:а|ов)?)?", text)
    if inches and (inches.group("whole") or inches.group("num")):
        return _quantize(_inch_value(inches.group("whole"), inches.group("num"), inches.group("den")))
    raise ValueError("Не удалось распознать размер. Примеры: 5'10\", 70, 20 1/2, 52 см.")


def _quantize(value):
    try:
        return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:  # pragma: no cover - защитный путь
        raise ValueError("Некорректное число.") from exc


def _fraction_text(value):
    """Decimal → «20 1/2» с точностью до 1/16 дюйма."""
    sixteenths = int((Decimal(value) * 16).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    whole, rest = divmod(sixteenths, 16)
    if rest == 0:
        return f"{whole}"
    frac = Fraction(rest, 16)
    return f"{whole} {frac.numerator}/{frac.denominator}" if whole else f"{frac.numerator}/{frac.denominator}"


def format_inches(value):
    if value is None:
        return None
    return f'{_fraction_text(value)}"'


def format_length(value):
    """70 → 5'10", 70.5 → 5'10 1/2", 108 → 9'0"."""
    if value is None:
        return None
    sixteenths = int((Decimal(value) * 16).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    feet, rest = divmod(sixteenths, 12 * 16)
    return f"{feet}'{_fraction_text(Decimal(rest) / 16)}\""


def format_dimensions(length_in, width_in, thickness_in=None):
    parts = [format_length(length_in), format_inches(width_in)]
    if thickness_in is not None:
        parts.append(format_inches(thickness_in))
    return " × ".join(p for p in parts if p)


def format_volume(volume_l):
    if volume_l is None:
        return None
    text = f"{Decimal(volume_l).normalize():f}".replace(".", ",")
    return f"{text} л"

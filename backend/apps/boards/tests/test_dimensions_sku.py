from decimal import Decimal

import pytest

from apps.boards.services.dimensions import format_dimensions, format_inches, format_length, format_volume, parse_inches
from apps.boards.services.sku import (build_sku, custom_type_sku_code, derive_shaper_code, length_code,
                                      normalize_suffix, width_code)


@pytest.mark.parametrize("raw, expected", [
    ("5'10\"", "70.00"), ("5’10”", "70.00"), ("5'10", "70.00"), ("5 ft 10", "70.00"), ("9'2\"", "110.00"),
    ("5'10 1/2\"", "70.50"), ("70", "70.00"), (70, "70.00"), ("20 1/2", "20.50"), ("20½", "20.50"),
    ('2 5/8"', "2.63"), ("2,75", "2.75"), ("52 см", "20.47"), ("1780 мм", "70.08"),
])
def test_parse_inches_accepts_shaper_notations(raw, expected):
    assert parse_inches(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", ["", "abc", "5'13\"", "1/0"])
def test_parse_inches_rejects_garbage(raw):
    with pytest.raises(ValueError):
        parse_inches(raw)


def test_feet_notation_can_be_disabled_for_widths():
    with pytest.raises(ValueError):
        parse_inches("5'10", feet_allowed=False)


def test_display_strings_use_feet_and_fractions():
    assert format_length(Decimal("70")) == "5'10\""
    assert format_length(Decimal("70.5")) == "5'10 1/2\""
    assert format_length(Decimal("108")) == "9'0\""
    assert format_inches(Decimal("20.5")) == '20 1/2"'
    assert format_inches(Decimal("2.625")) == '2 5/8"'
    assert format_inches(Decimal("22")) == '22"'
    assert format_dimensions(Decimal("70"), Decimal("20.5"), Decimal("2.625")) == "5'10\" × 20 1/2\" × 2 5/8\""
    assert format_dimensions(Decimal("70"), Decimal("20.5")) == "5'10\" × 20 1/2\""
    assert format_volume(Decimal("38.50")) == "38,5 л"


def test_sku_follows_prototype_format():
    sku = build_sku(shaper_code="KBA01", type_code="FSH", length_in=Decimal("70"), width_in=Decimal("20.5"), serial=3)
    assert sku == "GV-KBA01-FSH-5P10-W2050-003"
    assert build_sku(shaper_code="KBA01", type_code="LNG", length_in=Decimal("110"), width_in=Decimal("22"),
                     serial=1, suffix="EPS", version=2) == "GV-KBA01-LNG-9P2-W2200-001-EPS-V2"


def test_sku_length_and_width_codes():
    assert length_code(Decimal("70.5")) == "5P10D5"
    assert length_code(Decimal("120")) == "10P0"
    assert width_code(Decimal("19.75")) == "W1975"


def test_custom_type_code_is_stable_and_prefixed():
    code = custom_type_sku_code("Мини-малибу")
    assert code.startswith("X") and len(code) == 4
    assert code == custom_type_sku_code("мини-малибу ")


def test_suffix_normalization():
    assert normalize_suffix(" eps ") == "EPS"
    with pytest.raises(ValueError):
        normalize_suffix("эпокси")


def test_shaper_code_derived_from_name_and_unique():
    taken = {"KBA01"}
    assert derive_shaper_code("Kamchatka Boards", taken.__contains__) == "KBA02"
    assert derive_shaper_code("Волна", set().__contains__) == "VOL01"

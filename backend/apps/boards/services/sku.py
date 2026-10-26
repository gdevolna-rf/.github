"""Человекочитаемый артикул (BRD-05/06, ATX-08) — формат прототипа (SHAPERS_SCREENS.md §3.9).

    GV-<код шейпера>-<код типа>-<длина>-<ширина>-<NNN>[-<суффикс>][-V<версия>]
    GV-KBA01-FSH-5P10-W2050-003           5'10" × 20 1/2", модель №3 мастерской
    GV-KBA01-FSH-5P10D5-W2050-003-EPS     длина 5'10.5", суффикс EPS
    GV-KBA01-FSH-5P10-W2050-003-V2        вторая версия варианта (F10)

- код шейпера — стабильный WorkshopProfile.shaper_code (2–6 латинских букв/цифр);
- код типа — BoardType.sku_code (стандартные: SHT, FSH, FUN, MID, LNG, GUN, HYB, EGG, SFT, SUP; пользовательские: X + 3);
- длина — футы «P» дюймы, дробная часть дюйма через «D»: 70 → 5P10, 70.5 → 5P10D5;
- ширина — «W» + ширина × 100: 20.5 → W2050;
- NNN — постоянный порядковый номер модели в мастерской (BoardModel.serial), не меняется при правке типа/размеров.

Уникальность гарантирует БД (unique на BoardVariant.sku); IntegrityError переводится в 409 sku_conflict.
Внутренние UUID модели и варианта никогда не меняются.
"""
import re
from decimal import Decimal

from django.db.models import Max

from apps.common.text import transliterate

SKU_PREFIX = "GV"
SHAPER_CODE_RE = re.compile(r"^[A-Z0-9]{2,6}$")
SUFFIX_RE = re.compile(r"^[A-Z0-9]{1,8}$")
_BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _base36(number):
    if number == 0:
        return "0"
    out = ""
    while number:
        number, rem = divmod(number, 36)
        out = _BASE36[rem] + out
    return out


def custom_type_sku_code(name):
    """«X» + 3 символа base36 от 31-хеша названия (как в прототипе). Стабилен: сохраняется при создании типа."""
    h = 0
    for ch in name.strip().lower():
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return "X" + _base36(h)[-3:].rjust(3, "0")


def length_code(length_in):
    length_in = Decimal(length_in)
    feet = int(length_in // 12)
    inches = length_in - feet * 12
    whole = int(inches)
    frac = (inches - whole).normalize()
    code = f"{feet}P{whole}"
    if frac:
        code += "D" + format(frac, "f").split(".")[1]
    return code


def width_code(width_in):
    return f"W{int((Decimal(width_in) * 100).to_integral_value())}"


def normalize_suffix(value):
    value = (value or "").strip().upper()
    if value and not SUFFIX_RE.match(value):
        raise ValueError("Суффикс артикула — до 8 латинских букв и цифр.")
    return value


def build_sku(*, shaper_code, type_code, length_in, width_in, serial, suffix="", version=1):
    parts = [SKU_PREFIX, shaper_code, type_code or "CST", length_code(length_in), width_code(width_in), f"{serial:03d}"]
    if suffix:
        parts.append(suffix)
    if version and version > 1:
        parts.append(f"V{version}")
    return "-".join(parts)


def board_type_sku_code(board_type):
    if board_type.sku_code:
        return board_type.sku_code
    return custom_type_sku_code(board_type.name) if board_type.workshop_id else board_type.code[:3].upper()


def ensure_model_serial(model):
    """Назначает модели постоянный порядковый номер в мастерской (под блокировкой профиля мастерской)."""
    from apps.boards.models import BoardModel, WorkshopProfile

    if model.serial:
        return model.serial
    WorkshopProfile.objects.select_for_update().filter(organization_id=model.workshop_id).first()
    current = BoardModel.objects.filter(workshop_id=model.workshop_id).aggregate(m=Max("serial"))["m"] or 0
    model.serial = current + 1
    BoardModel.objects.filter(pk=model.pk).update(serial=model.serial)
    return model.serial


def compute_variant_sku(variant, *, model=None, board_type=None):
    """Артикул варианта по текущим атрибутам. Вызывать внутри transaction.atomic()."""
    from apps.boards.services.workshops import ensure_workshop_profile

    model = model or variant.model
    board_type = board_type or model.board_type
    profile = ensure_workshop_profile(model.workshop)
    serial = ensure_model_serial(model)
    return build_sku(
        shaper_code=profile.shaper_code, type_code=board_type_sku_code(board_type), length_in=variant.length_in,
        width_in=variant.width_in, serial=serial, suffix=variant.sku_suffix, version=variant.version,
    )


def derive_shaper_code(name, exists):
    """Код из названия: инициалы слов (до 3 букв) + номер 01…99 (затем 3 цифры). exists(code) -> bool."""
    words = [w for w in re.split(r"[^A-Z0-9]+", transliterate(name or "").upper()) if w]
    letters = "".join(w[0] for w in words if w[0].isalpha())[:3]
    if len(letters) < 3 and words:
        tail = "".join(ch for ch in words[0][1:] if ch.isalpha())
        letters = (letters + tail)[:3]
    letters = (letters or "SHP").ljust(3, "X")
    for n in range(1, 1000):
        candidate = f"{letters}{n:02d}" if n < 100 else f"{letters}{n:03d}"
        if not exists(candidate):
            return candidate
    raise RuntimeError("Не удалось подобрать код шейпера")  # pragma: no cover

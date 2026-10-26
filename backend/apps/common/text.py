"""Текстовые утилиты: человекочитаемые латинские slug из русских названий (NAV-05)."""
import re
import uuid

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}


def transliterate(value):
    return "".join(_TRANSLIT.get(ch, ch) for ch in value.lower())


def slugify_ru(value, max_length=60):
    slug = re.sub(r"[^a-z0-9]+", "-", transliterate(value)).strip("-")
    return slug[:max_length].strip("-") or uuid.uuid4().hex[:8]


def unique_slug(model, value, field="slug", max_length=60, **scope):
    """Уникальный slug в пределах модели (и scope-фильтра): base, base-2, base-3…"""
    base = slugify_ru(value, max_length=max_length - 4)
    candidate, n = base, 2
    while model.objects.filter(**{field: candidate}, **scope).exists():
        candidate, n = f"{base}-{n}", n + 1
    return candidate

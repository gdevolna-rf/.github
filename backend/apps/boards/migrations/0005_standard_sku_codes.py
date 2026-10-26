from django.db import migrations

# Коды типов в артикуле (формат прототипа, docs/prototype/SHAPERS_SCREENS.md §3.9).
SKU_CODES = {
    "shortboard": "SHT",
    "fish": "FSH",
    "funboard": "FUN",
    "midlength": "MID",
    "longboard": "LNG",
    "gun": "GUN",
    "hybrid": "HYB",
    "egg": "EGG",
    "softtop": "SFT",
    "sup": "SUP",
}


def forwards(apps, schema_editor):
    BoardType = apps.get_model("boards", "BoardType")
    for code, sku_code in SKU_CODES.items():
        BoardType.objects.filter(workshop=None, code=code).update(sku_code=sku_code)
    BoardType.objects.update_or_create(
        workshop=None, code="sup", defaults={"name": "SUP", "silhouette": "sup", "sort_order": 95, "sku_code": "SUP"}
    )


class Migration(migrations.Migration):
    dependencies = [("boards", "0004_sku_serial_cover")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

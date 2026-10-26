from django.db import migrations

BOARD_TYPES = [
    ("shortboard", "Шортборд", "shortboard", 10),
    ("fish", "Fish / Фиш", "fish", 20),
    ("funboard", "Фанборд", "funboard", 30),
    ("midlength", "Мидлленг", "midlength", 40),
    ("longboard", "Лонгборд", "longboard", 50),
    ("gun", "Gun / Ган", "gun", 60),
    ("hybrid", "Гибрид", "hybrid", 70),
    ("egg", "Эгг", "egg", 80),
    ("softtop", "Софттоп", "softtop", 90),
]
MATERIALS = ["PU / полиэстер", "EPS / эпоксид", "Карбон", "Софт (пена)", "Дерево"]


def forwards(apps, schema_editor):
    BoardType = apps.get_model("boards", "BoardType")
    Material = apps.get_model("boards", "Material")
    for code, name, silhouette, order in BOARD_TYPES:
        BoardType.objects.update_or_create(
            workshop=None, code=code, defaults={"name": name, "silhouette": silhouette, "sort_order": order}
        )
    for name in MATERIALS:
        Material.objects.get_or_create(workshop=None, name=name)


class Migration(migrations.Migration):
    dependencies = [("boards", "0002_initial")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

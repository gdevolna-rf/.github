from django.db import migrations

SPECIALTIES = [
    ("surfer", "Сёрфер", "Профиль сёрфера, бронирования, избранное и GG Surfer", 1),
    ("instructor", "Инструктор", "Расписание, ученики, занятия, отзывы и статистика", 2),
    ("shaper", "Шейпер", "Мастерская, модели досок, ремонт, обращения и статистика", 3),
    ("rental", "Прокат", "Инвентарь, доступность, выдача/возврат и бронирования", 4),
]


def forwards(apps, schema_editor):
    Specialty = apps.get_model("accounts", "Specialty")
    for code, name, description, order in SPECIALTIES:
        Specialty.objects.update_or_create(code=code, defaults={"name": name, "description": description, "sort_order": order})


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_initial")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

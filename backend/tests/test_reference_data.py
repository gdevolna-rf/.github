"""Тестовая инфраструктура: справочники data-миграций переживают transactional-тесты (backend/conftest.py).

Несколько transactional-тестов подряд: каждый видит справочники и может создавать строки в таблицах с
автоинкрементом (sequence выровнены после восстановления снимка). Обычные тесты после прогона тоже их видят.
"""
import pytest

from apps.accounts.models import Specialty
from apps.boards.models import BoardType, Material
from tests import reference_data
from tests.factories import WorkshopFactory


def _assert_reference_data_and_inserts_work():
    assert set(Specialty.objects.values_list("code", flat=True)) >= {"surfer", "instructor", "shaper", "rental"}
    assert BoardType.objects.filter(workshop=None, code="fish").exists()
    assert Material.objects.filter(workshop=None).count() >= 5
    workshop = WorkshopFactory()
    custom = BoardType.objects.create(workshop=workshop, code="custom-fish", name="Мой фиш", sku_code="CFS")
    assert custom.pk > BoardType.objects.filter(workshop=None).order_by("-pk").first().pk
    Material.objects.create(workshop=workshop, name="Пробка")


@pytest.mark.parametrize("attempt", range(3))
def test_reference_data_present_in_consecutive_transactional_tests(transactional_db, attempt):
    _assert_reference_data_and_inserts_work()


@pytest.mark.django_db(transaction=True)
def test_reference_data_present_with_transactional_marker():
    _assert_reference_data_and_inserts_work()


def test_reference_data_present_in_regular_test(db):
    _assert_reference_data_and_inserts_work()
    assert not reference_data.reference_data_missing()

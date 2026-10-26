"""Idempotency-Key (9.1, apps.common.idempotency): один ключ — одна запись и один ответ, в том числе при гонке.

run_idempotent сам берёт pg_advisory_xact_lock по (аккаунт, endpoint, ключ): параллельный повтор ждёт коммита
первого запроса и получает сохранённый ответ, а не создаёт дубль. Нужны настоящие параллельные транзакции —
поэтому transactional_db (справочники восстанавливает фикстура reference_data из backend/conftest.py).
"""
import json
import threading

from django.db import connection

from apps.commerce.models import Inquiry
from apps.common.models import IdempotencyRecord
from apps.messaging.models import Message
from tests.factories import BoardModelFactory, BoardVariantFactory, WorkshopFactory


def _parallel(n, func):
    barrier = threading.Barrier(n)
    results = [None] * n

    def worker(index):
        try:
            barrier.wait(timeout=10)
            results[index] = func()
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


def test_parallel_inquiries_with_same_key_create_one_record_and_same_response(transactional_db, make_client):
    model = BoardModelFactory(workshop=WorkshopFactory())
    BoardVariantFactory(model=model)
    customer = make_client()
    payload = {"kind": "board_purchase", "target_type": "board_model", "target_id": str(model.pk),
               "message": "Здравствуйте! Есть ли доска в наличии?"}

    def post():
        response = customer.post("/api/v1/inquiries", payload, format="json", HTTP_IDEMPOTENCY_KEY="race-key-1")
        return response.status_code, response.content, response.get("Idempotent-Replay")

    outcomes = _parallel(2, post)
    assert [code for code, _, _ in outcomes] == [201, 201], outcomes
    assert json.loads(outcomes[0][1]) == json.loads(outcomes[1][1])  # тот же ответ (jsonb не хранит порядок ключей)
    assert sorted(str(replay) for _, _, replay in outcomes) == ["None", "true"]
    assert IdempotencyRecord.objects.filter(key="race-key-1", account=customer.account).count() == 1
    assert Inquiry.objects.filter(customer=customer.account).count() == 1
    assert Message.objects.filter(conversation__inquiry__customer=customer.account).count() == 1


def test_sequential_replay_returns_identical_body_and_mismatch_is_409(db, make_client):
    model = BoardModelFactory(workshop=WorkshopFactory())
    BoardVariantFactory(model=model)
    client = make_client()
    payload = {"kind": "board_purchase", "target_type": "board_model", "target_id": str(model.pk), "message": "Привет"}
    first = client.post("/api/v1/inquiries", payload, format="json", HTTP_IDEMPOTENCY_KEY="k-2")
    second = client.post("/api/v1/inquiries", payload, format="json", HTTP_IDEMPOTENCY_KEY="k-2")
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json() and second["Idempotent-Replay"] == "true"
    other = client.post("/api/v1/inquiries", {**payload, "message": "Другое"}, format="json",
                        HTTP_IDEMPOTENCY_KEY="k-2")
    assert other.status_code == 409 and other.json()["error"]["code"] == "idempotency_mismatch"
    # Тот же ключ у другого пользователя — независимая операция.
    assert make_client().post("/api/v1/inquiries", payload, format="json",
                              HTTP_IDEMPOTENCY_KEY="k-2").status_code == 201
    assert Inquiry.objects.count() == 2

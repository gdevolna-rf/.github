"""OpenAPI-схема (docs/openapi.yml): генерируется без ошибок и предупреждений, имена перечислений стабильны."""
import re

import pytest
import yaml
from django.core.management import call_command


@pytest.fixture(scope="module")
def schema(tmp_path_factory):
    path = tmp_path_factory.mktemp("schema") / "openapi.yml"
    # --fail-on-warn: любое новое предупреждение (коллизия имён, неописанное поле) роняет тест.
    call_command("spectacular", "--file", str(path), "--validate", "--fail-on-warn")
    return yaml.safe_load(path.read_text())


def test_schema_has_no_hash_named_enums_and_stable_shared_enums(schema):
    components = schema["components"]["schemas"]
    hashed = [name for name in components if re.search(r"[0-9A-Fa-f]{3}Enum$", name)
              and any(ch.isdigit() for ch in name[-7:-4])]
    assert hashed == []
    for name in ("BookingStatusEnum", "InquiryStatusEnum", "NotificationKindEnum", "MediaPurposeEnum",
                 "OrganizationStatusEnum", "ClubEventStatusEnum", "RidingLevelEnum"):
        assert name in components, name
    assert {"event_status", "product_available"} <= set(components["NotificationKindEnum"]["enum"])


def test_session_cookie_security_scheme(schema):
    assert schema["components"]["securitySchemes"]["cookieAuth"]["in"] == "cookie"
    assert schema["paths"]["/api/v1/me"]["get"]["security"] == [{"cookieAuth": []}]


def test_operation_ids_are_unique(schema):
    ids = [operation["operationId"] for item in schema["paths"].values() for operation in item.values()
           if isinstance(operation, dict) and "operationId" in operation]
    assert len(ids) == len(set(ids))
    assert "me_instructor_media_reorder" in ids and "staff_roles_revoke" in ids

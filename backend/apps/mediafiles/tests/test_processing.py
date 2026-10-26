"""Юнит-проверки сигнатур и правил назначения медиа."""
import pytest

from apps.mediafiles import policy
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.services.processing import sniff_content_type
from apps.mediafiles.tests.utils import MOV_BYTES, MP4_BYTES, PDF_BYTES, WEBM_BYTES, make_image


@pytest.mark.parametrize("data,expected", [
    (make_image("JPEG"), "image/jpeg"),
    (make_image("PNG"), "image/png"),
    (make_image("WEBP"), "image/webp"),
    (PDF_BYTES, "application/pdf"),
    (MP4_BYTES, "video/mp4"),
    (MOV_BYTES, "video/quicktime"),
    (WEBM_BYTES, "video/webm"),
    (b"GIF89a....", None),
    (b"<svg xmlns=...>", None),
    (b"", None),
])
def test_sniff_content_type(data, expected):
    assert sniff_content_type(data[:64]) == expected


def test_every_user_purpose_has_allowed_kinds():
    for purpose in MediaAsset.Purpose.values:
        if purpose in policy.SERVER_ONLY_PURPOSES:
            continue
        assert policy.PURPOSE_KINDS[purpose], purpose


def test_private_purposes_mapping():
    assert policy.visibility_for("certificate") == "private"
    assert policy.visibility_for("data_export") == "private"
    assert policy.visibility_for("board_photo") == "public"
    assert policy.visibility_for("avatar") == "public"


def test_key_layout():
    key = policy.build_key("board_photo", "image/webp")
    parts = key.split("/")
    assert parts[0] == "public" and parts[1] == "board_photo" and len(parts[2]) == 4 and len(parts[3]) == 2
    assert parts[4].endswith(".webp")
    assert policy.thumbnail_key_for(key) == key + ".thumb.webp"

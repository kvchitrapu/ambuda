import json
import pytest

from ambuda.models.proofing import LanguageCode
from ambuda.views.proofing.publish import _validate_slug


@pytest.mark.parametrize(
    "slug",
    [
        "ramayana",
        "a-b-c",
        "text123",
        "vol-1-ch-2",
        "a",
        "1",
    ],
)
def test_validate_slug_valid(slug):
    assert _validate_slug(slug) is None


@pytest.mark.parametrize(
    "slug",
    [
        "",
        "-bad",
        "bad-",
        "has--double",
        "Upper",
        "has space",
        "rāmāyaṇa",
        "has_underscore",
        "has.dot",
        "-",
        "---",
    ],
)
def test_validate_slug_invalid(slug):
    assert _validate_slug(slug) is not None


@pytest.mark.parametrize("code", list(LanguageCode))
def test_valid_language_codes(code):
    assert isinstance(code.label, str)
    assert len(code.label) > 0


def test_publish_config_post__invalid_filter(rama_client):
    config_list = [
        {"slug": "test-text", "title": "Test", "target": "(image 1"},
    ]
    resp = rama_client.post(
        "/proofing/test-project/publish",
        data={"config": json.dumps(config_list)},
    )
    assert resp.status_code == 302

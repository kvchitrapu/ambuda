import pytest

from ambuda.utils.slug import title_to_slug


@pytest.mark.parametrize(
    "input_,expected",
    [
        ("रामायणम्", "ramayanam"),
        ("विष्णुपुराणम्", "vishnupuranam"),
        ("राम चरित", "rama-carita"),
        ("ramayana", "ramayana"),
        ("Rāmāyaṇa", "ramayana"),
        ("", ""),
        ("--hello--", "hello"),
        ("foo   bar", "foo-bar"),
        ("अङ्गम्", "angam"),
        ("पञ्चतन्त्रम्", "pancatantram"),
        ("सम्पदा", "sampada"),
        ("सम्बन्धः", "sambandhah"),
        ("संशय", "samshaya"),
        ("संस्कृतम्", "samskrtam"),
        ("संगीतम्", "sangitam"),
        ("सिंहः", "simhah"),
    ],
)
def test_title_to_slug(input_, expected):
    assert title_to_slug(input_) == expected

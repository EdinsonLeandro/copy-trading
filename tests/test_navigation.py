from src.scraper.navigation import parse_page_info


class _FakeLabelElement:
    def __init__(self, text, visible=True):
        self._text = text
        self._visible = visible

    def count(self):
        return 1 if self._text is not None else 0

    def is_visible(self):
        return self._visible

    def inner_text(self):
        return self._text


class _FakeLocator:
    def __init__(self, label_element):
        self._label_element = label_element

    @property
    def first(self):
        return self._label_element


class _FakeContainer:
    def __init__(self, label_text=None, visible=True):
        self._label_element = _FakeLabelElement(label_text, visible)

    def locator(self, _selector):
        return _FakeLocator(self._label_element)


def test_parse_page_info_page_of_format():
    container = _FakeContainer("Page 1 of 105")
    assert parse_page_info(container) == (1, 105)


def test_parse_page_info_range_format():
    container = _FakeContainer("1 – 20 of 2100")
    assert parse_page_info(container) == (1, 105)


def test_parse_page_info_missing_label_defaults_to_one_page():
    container = _FakeContainer(None)
    assert parse_page_info(container) == (1, 1)


def test_parse_page_info_hidden_label_defaults_to_one_page():
    container = _FakeContainer("Page 1 of 105", visible=False)
    assert parse_page_info(container) == (1, 1)


def test_parse_page_info_unrecognized_text_defaults_to_one_page():
    container = _FakeContainer("no pagination info here")
    assert parse_page_info(container) == (1, 1)

from src.common.csv_store import append_rows, init_csv_file, load_existing_ids

HEADERS = ["name", "trader_id", "profile_url"]
ID_FIELDS = ("trader_id", "profile_url")


def test_load_existing_ids_missing_file_returns_empty_set(tmp_path):
    assert load_existing_ids(tmp_path / "does_not_exist.csv", ID_FIELDS) == set()


def test_init_csv_file_writes_headers(tmp_path):
    csv_path = tmp_path / "traders.csv"
    init_csv_file(csv_path, HEADERS)

    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",") == HEADERS


def test_init_csv_file_does_not_overwrite_existing_data(tmp_path):
    csv_path = tmp_path / "traders.csv"
    init_csv_file(csv_path, HEADERS)
    append_rows([{"name": "Alice", "trader_id": "1"}], csv_path, HEADERS)

    init_csv_file(csv_path, HEADERS)  # should be a no-op since the file already has content

    rows = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2


def test_append_and_reload_ids(tmp_path):
    csv_path = tmp_path / "traders.csv"
    append_rows(
        [
            {"name": "Alice", "trader_id": "1", "profile_url": "http://x/1"},
            {"name": "Bob", "trader_id": "2", "profile_url": "http://x/2"},
        ],
        csv_path,
        HEADERS,
    )

    seen = load_existing_ids(csv_path, ID_FIELDS)
    assert seen == {"1", "http://x/1", "2", "http://x/2"}


def test_append_rows_ignores_unknown_fields(tmp_path):
    csv_path = tmp_path / "traders.csv"
    append_rows([{"name": "Alice", "trader_id": "1", "unexpected_field": "x"}], csv_path, HEADERS)

    seen = load_existing_ids(csv_path, ID_FIELDS)
    assert "1" in seen


def test_append_rows_empty_list_is_noop(tmp_path):
    csv_path = tmp_path / "traders.csv"
    append_rows([], csv_path, HEADERS)

    assert not csv_path.exists()


def test_load_existing_ids_only_reads_requested_fields(tmp_path):
    csv_path = tmp_path / "traders.csv"
    append_rows([{"name": "Alice", "trader_id": "1", "profile_url": "http://x/1"}], csv_path, HEADERS)

    seen = load_existing_ids(csv_path, ("trader_id",))
    assert seen == {"1"}

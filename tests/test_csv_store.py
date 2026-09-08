from src.scraper.csv_store import (
    CSV_HEADERS,
    append_profiles_to_csv,
    init_csv_file,
    load_existing_trader_ids,
)


def test_load_existing_trader_ids_missing_file_returns_empty_set(tmp_path):
    assert load_existing_trader_ids(tmp_path / "does_not_exist.csv") == set()


def test_init_csv_file_writes_headers(tmp_path):
    csv_path = tmp_path / "traders.csv"
    init_csv_file(csv_path)

    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",") == CSV_HEADERS


def test_init_csv_file_does_not_overwrite_existing_data(tmp_path):
    csv_path = tmp_path / "traders.csv"
    init_csv_file(csv_path)
    append_profiles_to_csv([{"name": "Alice", "trader_id": "1"}], csv_path)

    init_csv_file(csv_path)  # should be a no-op since the file already has content

    rows = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2


def test_append_and_reload_trader_ids(tmp_path):
    csv_path = tmp_path / "traders.csv"
    append_profiles_to_csv(
        [
            {"name": "Alice", "trader_id": "1", "profile_url": "http://x/1"},
            {"name": "Bob", "trader_id": "2", "profile_url": "http://x/2"},
        ],
        csv_path,
    )

    seen = load_existing_trader_ids(csv_path)
    assert seen == {"1", "http://x/1", "2", "http://x/2"}


def test_append_profiles_ignores_unknown_fields(tmp_path):
    csv_path = tmp_path / "traders.csv"
    append_profiles_to_csv([{"name": "Alice", "trader_id": "1", "unexpected_field": "x"}], csv_path)

    seen = load_existing_trader_ids(csv_path)
    assert "1" in seen


def test_append_profiles_empty_list_is_noop(tmp_path):
    csv_path = tmp_path / "traders.csv"
    append_profiles_to_csv([], csv_path)

    assert not csv_path.exists()

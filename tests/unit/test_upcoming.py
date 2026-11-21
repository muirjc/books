"""Spec 007: the date rules for "Coming" and "Now out", and parsing the new form fields."""

from __future__ import annotations

from datetime import date, timedelta

from starlette.datastructures import FormData

from book_tracker.domain.values import NOW_OUT_DAYS, is_now_out, is_upcoming
from book_tracker.web.forms import parse_add_book, parse_entry_update

TODAY = date(2026, 11, 21)


def test_upcoming_is_strictly_after_today() -> None:
    assert is_upcoming(TODAY + timedelta(days=1), TODAY)
    assert not is_upcoming(TODAY, TODAY)
    assert not is_upcoming(TODAY - timedelta(days=1), TODAY)
    assert not is_upcoming(None, TODAY)


def test_now_out_is_release_day_through_day_thirty() -> None:
    assert NOW_OUT_DAYS == 30
    assert is_now_out(TODAY, TODAY)  # day 1
    assert is_now_out(TODAY - timedelta(days=29), TODAY)  # day 30
    assert not is_now_out(TODAY - timedelta(days=30), TODAY)  # day 31
    assert not is_now_out(TODAY + timedelta(days=1), TODAY)
    assert not is_now_out(None, TODAY)


def _add(**fields: str) -> FormData:
    base = {"title": "T", "author_name_0": "A", "status": "want_to_read"}
    return FormData({**base, **fields})


def test_add_book_parses_release_date_and_pre_ordered() -> None:
    form = parse_add_book(_add(release_date="2027-03-03", pre_ordered="yes"))
    assert form.release_date == date(2027, 3, 3)
    assert form.pre_ordered is True
    assert "release_date" not in form.errors


def test_add_book_defaults() -> None:
    form = parse_add_book(_add())
    assert form.release_date is None
    assert form.pre_ordered is False


def test_add_book_bad_release_date() -> None:
    for bad in ("2027-02-30", "soon", "03/03/2027"):
        form = parse_add_book(_add(release_date=bad))
        assert form.errors["release_date"] == "Enter a date like 2027-03-01", bad


def test_pre_ordered_last_value_wins() -> None:
    ticked = parse_add_book(FormData([("title", "T"), ("author_name_0", "A"),
                                      ("pre_ordered", ""), ("pre_ordered", "yes")]))  # fmt: skip
    assert ticked.pre_ordered is True
    unticked = parse_add_book(FormData([("title", "T"), ("author_name_0", "A"),
                                        ("pre_ordered", "")]))  # fmt: skip
    assert unticked.pre_ordered is False


def test_entry_update_pre_ordered_only_when_present() -> None:
    update, errors, _ = parse_entry_update(FormData({"status": "reading"}))
    assert update is not None and not errors
    assert "pre_ordered" not in update.model_fields_set
    update, _, _ = parse_entry_update(FormData({"pre_ordered": "yes"}))
    assert update is not None and update.pre_ordered is True
    update, _, _ = parse_entry_update(FormData({"pre_ordered": ""}))
    assert update is not None and update.pre_ordered is False

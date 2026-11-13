"""Validate the shared mathematical case catalogue without using the engine."""

import csv
from pathlib import Path

import pytest


CASES_PATH = Path(__file__).with_name("cases.csv")
REQUIRED_COLUMNS = (
    "case_id",
    "category",
    "previous_step",
    "current_step",
    "expected_status",
    "expected_mistake",
    "expected_reason",
    "notes",
)
ALLOWED_STATUSES = {"valid", "invalid", "unknown"}
ALLOWED_MISTAKES = {
    "one_side_only",
    "sign_error",
    "wrong_inverse_op",
    "arithmetic_error",
    "partial_distribution",
    "coefficient_error",
    "exponent_error",
    "divide_by_variable",
    "lost_solution",
    "extra_solution",
}
FOUNDATIONAL_CASES = {
    ("x + 5 = 9", "x = 4"): ("valid", ""),
    ("x + 5 = 9", "x = 5"): ("invalid", "arithmetic_error"),
    ("2x = 8", "x = 4"): ("valid", ""),
    ("2x = 8", "x = 5"): ("invalid", "arithmetic_error"),
    ("2(x + 3) = 10", "2x + 6 = 10"): ("valid", ""),
    ("2x + 6 = 10", "2x = 4"): ("valid", ""),
    ("x^2 = 1", "x = 1"): ("invalid", "lost_solution"),
    ("x + 2 = 5", "5 = x + 2"): ("valid", ""),
    ("x/2 = 3", "x = 6"): ("valid", ""),
    ("x^2 = x", "x = 1"): ("invalid", "divide_by_variable"),
    ("2(x+3) = 10", "2x+3 = 10"): ("invalid", "partial_distribution"),
    ("x+5 = 9", "x = 14"): ("invalid", "sign_error"),
}


@pytest.fixture(scope="module")
def catalogue():
    with CASES_PATH.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = reader.fieldnames
        rows = list(reader)
    return columns, rows


def test_cases_csv_exists():
    assert CASES_PATH.is_file()


def test_cases_csv_opens_as_utf8():
    with CASES_PATH.open("r", encoding="utf-8", newline="") as csv_file:
        assert next(csv.reader(csv_file), None) is not None


def test_cases_csv_has_required_columns(catalogue):
    columns, _ = catalogue
    assert columns == list(REQUIRED_COLUMNS)


def test_catalogue_has_at_least_42_cases(catalogue):
    _, rows = catalogue
    assert len(rows) >= 42


def test_catalogue_has_at_least_30_m3_authored_cases(catalogue):
    _, rows = catalogue
    m3_rows = [row for row in rows if row["case_id"].startswith("M3_")]
    assert len(m3_rows) >= 30


def test_case_ids_are_unique(catalogue):
    _, rows = catalogue
    case_ids = [row["case_id"] for row in rows]
    assert len(case_ids) == len(set(case_ids))


def test_previous_and_current_steps_are_nonempty(catalogue):
    _, rows = catalogue
    assert all(row["previous_step"].strip() for row in rows)
    assert all(row["current_step"].strip() for row in rows)


def test_expected_statuses_are_allowed(catalogue):
    _, rows = catalogue
    assert all(row["expected_status"] in ALLOWED_STATUSES for row in rows)


def test_nonempty_mistake_labels_are_allowed(catalogue):
    _, rows = catalogue
    assert all(
        not row["expected_mistake"] or row["expected_mistake"] in ALLOWED_MISTAKES
        for row in rows
    )


def test_valid_cases_have_no_expected_mistake_label(catalogue):
    _, rows = catalogue
    assert all(
        not row["expected_mistake"]
        for row in rows
        if row["expected_status"] == "valid"
    )


def test_unconfirmed_m3_mistake_labels_remain_blank(catalogue):
    _, rows = catalogue
    by_id = {row["case_id"]: row for row in rows}

    assert by_id["M3_009"]["expected_status"] == "invalid"
    assert by_id["M3_009"]["expected_mistake"] == ""
    assert by_id["M3_011"]["expected_status"] == "invalid"
    assert by_id["M3_011"]["expected_mistake"] == ""


def test_previous_current_pairs_are_unique(catalogue):
    _, rows = catalogue
    pairs = [(row["previous_step"], row["current_step"]) for row in rows]
    assert len(pairs) == len(set(pairs))


def test_foundational_cases_are_present_with_expected_ground_truth(catalogue):
    _, rows = catalogue
    actual = {
        (row["previous_step"], row["current_step"]): (
            row["expected_status"],
            row["expected_mistake"],
        )
        for row in rows
    }
    for equation_pair, expected in FOUNDATIONAL_CASES.items():
        assert actual.get(equation_pair) == expected


def test_expected_reasons_are_nonempty(catalogue):
    _, rows = catalogue
    assert all(row["expected_reason"].strip() for row in rows)


def test_catalogue_has_no_malformed_or_missing_required_fields(catalogue):
    columns, rows = catalogue
    assert columns == list(REQUIRED_COLUMNS)
    assert rows, "The catalogue must contain data rows."

    required_nonempty = {
        "case_id",
        "category",
        "previous_step",
        "current_step",
        "expected_status",
        "expected_reason",
    }
    for row_number, row in enumerate(rows, start=2):
        assert None not in row, f"Row {row_number} contains extra CSV fields."
        assert all(value is not None for value in row.values()), (
            f"Row {row_number} is missing one or more CSV fields."
        )
        assert all(row[column].strip() for column in required_nonempty), (
            f"Row {row_number} has an empty required field."
        )


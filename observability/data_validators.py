from typing import Tuple

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

# ── Schemas ────────────────────────────────────────────────────────────────────

SCRAPE_SCHEMA = pa.DataFrameSchema(
    {
        "name": pa.Column(str, nullable=True),
    },
    name="ScrapedProductSchema",
    coerce=True,
)

RFM_INPUT_SCHEMA = pa.DataFrameSchema(
    {
        "customer_id":      pa.Column(str,          nullable=False),
        "transaction_date": pa.Column(pa.DateTime,  nullable=False),
        "price":            pa.Column(float, pa.Check.greater_than(0),
                                     nullable=False, coerce=True),
    },
    name="RFMInputSchema",
    coerce=True,
)

RFM_OUTPUT_SCHEMA = pa.DataFrameSchema(
    {
        "customer_id": pa.Column(str,  nullable=False),
        "recency":     pa.Column(int,  pa.Check.greater_than_or_equal_to(0),
                                 nullable=False),
        "frequency":   pa.Column(int,  pa.Check.greater_than(0),
                                 nullable=False),
        "monetary":    pa.Column(float, pa.Check.greater_than(0),
                                 nullable=False),
    },
    name="RFMOutputSchema",
    coerce=True,
)

SURVIVAL_INPUT_SCHEMA = pa.DataFrameSchema(
    {
        "customer_id":    pa.Column(str,  nullable=False),
        "duration":       pa.Column(int,  pa.Check.greater_than(0),
                                   nullable=False),
        "event_observed": pa.Column(bool, nullable=False),
    },
    name="SurvivalInputSchema",
    coerce=True,
)


# ── Validation helpers ─────────────────────────────────────────────────────────

def validate_df(
    df: pd.DataFrame,
    schema: pa.DataFrameSchema,
    label: str = "",
) -> Tuple[bool, int]:
    """
    Validate df against schema using lazy evaluation (all errors collected).

    Prints a warning on failure but does NOT raise — returns (is_valid, error_count).
    """
    try:
        schema.validate(df, lazy=True)
        return True, 0
    except SchemaErrors as exc:
        n_errors = len(exc.failure_cases) if exc.failure_cases is not None else 1
        tag = f"[{label}] " if label else ""
        print(
            f"⚠️  {tag}Validation failed against '{schema.name}': "
            f"{n_errors} failure(s).\n{exc.failure_cases}"
        )
        return False, n_errors
    except Exception as exc:
        print(f"⚠️  Unexpected validation error: {exc}")
        return False, 1


def validate_rfm_input(df: pd.DataFrame) -> Tuple[bool, int]:
    """Validate a raw transactions DataFrame against RFM_INPUT_SCHEMA."""
    return validate_df(df, RFM_INPUT_SCHEMA, label="RFM input")


def validate_rfm_output(df: pd.DataFrame) -> Tuple[bool, int]:
    """Validate a computed RFM DataFrame against RFM_OUTPUT_SCHEMA."""
    return validate_df(df, RFM_OUTPUT_SCHEMA, label="RFM output")


def get_validation_report(df: pd.DataFrame, schema_name: str) -> dict:
    """Return a lightweight data-quality snapshot of df."""
    return {
        "schema":      schema_name,
        "rows":        len(df),
        "columns":     list(df.columns),
        "null_counts": df.isnull().sum().to_dict(),
        "dtypes":      df.dtypes.astype(str).to_dict(),
    }


# ── main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df = pd.DataFrame({
        "customer_id":      ["C1", "C2", "C3"],
        "transaction_date": pd.to_datetime(["2022-01-01", "2022-02-01", "2022-03-01"]),
        "price":            [10.5, 20.0, 5.0],
    })

    valid, errors = validate_rfm_input(df)
    print("RFM input valid:", valid, "| Errors:", errors)
    print("Validators OK")

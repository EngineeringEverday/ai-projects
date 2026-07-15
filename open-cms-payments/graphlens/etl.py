#! usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GraphLens ETL
=============
Transforms raw CMS Open Payments CSV downloads into a set of compressed
Parquet files that serve as the graph database for GraphLens.

Output files (all written to PROCESSED_DIR/)
--------------------------------------------
  nodes.parquet              - all unique entity nodes (physicians, hospitals, manufacturers)
  node_products.parquet      - unpivoted drug/device product associations per edge record
  edges_general.parquet      - aggregated General Payment edges (src→dst per year)
  edges_research.parquet     - Research Payment edges (direct recipient + PI edges)
  edges_ownership.parquet    - Physician Ownership Interest edges
  record_ids_general.parquet - raw Record_ID dedup table for incremental loads

Schema notes
------------
  Nodes        : id (string), node_type, profile_id, name, first_name, last_name,
                 credential_type, specialty (primary), specialties (pipe-joined 1-6),
                 state, city, zip_code, country
  Edges        : src_id, dst_id, year, record_id, date_of_payment, payment_month,
                 total_amount, payment_count, form_of_payment, natures,
                 disputed_count, ownership_flag, delay_count,
                 third_party_count, products (pipe-joined drug/device names)
  Research +   : study_name, clinical_trial_id
  Ownership +  : family_member_flag, nature_of_interest

Design principles
-----------------
- Read CSVs lazily (Polars LazyFrame): column pruning happens at CSV scan level.
- All type-casting is explicit and strict=False to tolerate CMS quirks.
- UNCHANGED rows are dropped at read time (pre-2024 files include re-publications).
- CHANGED rows are tracked via Record_ID so the API can do upserts if needed.
- Multi-value drug/device slots (_1 to _5) are unpivoted into node_products.parquet.
- Specialty slots (_1 to _6) are pipe-joined into a single `specialties` column
  and the first non-null value becomes `specialty` (the primary graph attribute).

Usage
-----
  uv run python -m graphlens.etl              # all configured years
  uv run python -m graphlens.etl --year 2023  # single year
"""

import glob
from pathlib import Path

import polars as pl     # type: ignore[import-not-found]
from polars import col

from graphlens.config import (
    DATA_DIR, PROCESSED_DIR, PROGRAM_YEARS,
    nodes_path, edges_path, research_path, ownership_path,
)


# Parquet paths for the new outputs this ETL adds
def node_products_path() -> Path:
    return PROCESSED_DIR / "node_products.parquet"


def record_ids_path() -> Path:
    return PROCESSED_DIR / "record_ids_general.parquet"


# CMS CSV column name constants
# Manufacturer / GPO
MFR_ID = "Applicable_Manufacturer_or_Applicable_GPO_Making_Payment_ID"
MFR_NAME = "Applicable_Manufacturer_or_Applicable_GPO_Making_Payment_Name"
MFR_ST = "Applicable_Manufacturer_or_Applicable_GPO_Making_Payment_State"
MFR_COUNTRY = "Applicable_Manufacturer_or_Applicable_GPO_Making_Payment_Country"
MFR_SUB = "Submitting_Applicable_Manufacturer_or_Applicable_GPO_Name"

# Recipient identity
NPI = "Covered_Recipient_NPI"
PROFILE_ID = "Covered_Recipient_Profile_ID"
PHYS_NPI = "Physician_NPI"       # Ownership CSV only
PHYS_PROF = "Covered_Recipient_Profile_ID"  # also in Ownership CSV
CCN = "Teaching_Hospital_CCN"
RCPT_TYPE = "Covered_Recipient_Type"

# Recipient name / credential
FNAME = "Covered_Recipient_First_Name"
MNAME = "Covered_Recipient_Middle_Name"
LNAME = "Covered_Recipient_Last_Name"
SUFFIX = "Covered_Recipient_Name_Suffix"
CRED1 = "Covered_Recipient_Primary_Type_1"

# Specialty slots 1–6
SPEC_COLS = [f"Covered_Recipient_Specialty_{i}" for i in range(1, 7)]
# License state slots 1–5
LIC_COLS = [f"Covered_Recipient_License_State_code{i}" for i in range(1, 6)]

# Recipient location
RCPT_ST = "Recipient_State"
RCPT_CTY = "Recipient_City"
RCPT_ZIP = "Recipient_Zip_Code"
RCPT_CTRY = "Recipient_Country"

# Teaching hospital
HOSP_NM = "Teaching_Hospital_Name"
HOSP_TH_ID = "Teaching_Hospital_ID"

# Edge core
RECORD_ID = "Record_ID"
CHANGE = "Change_Type"
YEAR_COL = "Program_Year"
DATE_PAY = "Date_of_Payment"
AMOUNT = "Total_Amount_of_Payment_USDollars"
PAY_N = "Number_of_Payments_Included_in_Total_Amount"
FORM = "Form_of_Payment_or_Transfer_of_Value"
NATURE = "Nature_of_Payment_or_Transfer_of_Value"

# Edge flags
DISPUTE = "Dispute_Status_for_Publication"
OWN_IND = "Physician_Ownership_Indicator"
DELAY = "Delay_in_Publication_Indicator"
THIRD_PARTY = "Third_Party_Payment_Recipient_Indicator"
THIRD_NM = "Name_of_Third_Party_Entity_Receiving_Payment_or_Transfer_of_Value"
CHARITY = "Charity_Indicator"

# Travel (General payments only)
TRAVEL_CITY = "City_of_Travel"
TRAVEL_STATE = "State_of_Travel"
TRAVEL_CTRY = "Country_of_Travel"

# Drug / device slots (1–5 in General; 1–5 in Research)
N_PRODUCT_SLOTS = 5
DRUG_NAME_COLS = [f"Name_of_Associated_Covered_Drug_or_Biological_{i}" for i in range(1, N_PRODUCT_SLOTS + 1)]
DRUG_NDC_COLS = [f"NDC_of_Associated_Covered_Drug_or_Biological_{i}" for i in range(1, N_PRODUCT_SLOTS + 1)]
DEV_NAME_COLS = [f"Name_of_Associated_Covered_Device_or_Medical_Supply_{i}" for i in range(1, N_PRODUCT_SLOTS + 1)]

# Newer CMS schema uses a single product name column per slot + product-type indicator
PROD_IND_COLS = [f"Indicate_Drug_or_Biological_or_Device_or_Medical_Supply_{i}" for i in range(1, N_PRODUCT_SLOTS + 1)]
PROD_NAME_COLS = [f"Name_of_Drug_or_Biological_or_Device_or_Medical_Supply_{i}" for i in range(1, N_PRODUCT_SLOTS + 1)]
PROD_NDC_COLS = [f"Associated_Drug_or_Biological_NDC_{i}" for i in range(1, N_PRODUCT_SLOTS + 1)]

# Research-only
STUDY_NAME = "Name_of_Study"
CT_ID = "ClinicalTrials_Gov_Identifier"
CT_LINK = "Research_Information_Link"

# PI slots 1–5 (Research CSV)
N_PI_SLOTS = 5
PI_NPI_COLS = [f"Principal_Investigator_{i}_NPI" for i in range(1, N_PI_SLOTS + 1)]
PI_PROF_COLS = [f"Principal_Investigator_{i}_Profile_ID" for i in range(1, N_PI_SLOTS + 1)]
PI_FNAME_COLS = [f"Principal_Investigator_{i}_First_Name" for i in range(1, N_PI_SLOTS + 1)]
PI_LNAME_COLS = [f"Principal_Investigator_{i}_Last_Name" for i in range(1, N_PI_SLOTS + 1)]
PI_CRED_COLS = [f"Principal_Investigator_{i}_Primary_Type_1" for i in range(1, N_PI_SLOTS + 1)]
PI_SPEC_COLS = [f"Principal_Investigator_{i}_Specialty_1" for i in range(1, N_PI_SLOTS + 1)]

# Ownership
OWN_FAMILY = "Interest_Held_by_Physician_or_an_Immediate_Family_Member"
OWN_NATURE = "Nature_of_Interest"
OWN_VALUE = "Value_of_Interest"


# Utilities
def _lazy_columns(lf: pl.LazyFrame) -> set[str]:
    return set(lf.collect_schema().names())


def _find_csv(year: int, pattern: str) -> Path | None:
    hits = glob.glob(str(DATA_DIR / str(year) / f"*{pattern}*PGYR{year}*.csv"))
    return Path(hits[0]) if hits else None


def _present(cols: list[str], schema: set[str]) -> list[str]:
    """Return only the columns that actually exist in the CSV schema."""
    return [c for c in cols if c in schema]


def _read_csv_lazy(path: Path, columns: list[str]) -> pl.LazyFrame:
    """
    Open a CMS CSV lazily with Polars.  Only the requested columns are read.
    UNCHANGED records are dropped immediately.
    All columns are read as Utf8 (infer_schema=False) to avoid dtype failures
    on fields like ZIP+4 (e.g. "32256-6932") or mixed-type NPI fields.
    """
    all_cols = set(
        pl.scan_csv(path, has_header=True, infer_schema=False)
          .collect_schema().names()
    )
    use_cols = [c for c in columns if c in all_cols]

    lf = pl.scan_csv(
        path,
        has_header=True,
        infer_schema=False,
        low_memory=False,
    ).select(use_cols)

    if CHANGE in use_cols:
        lf = lf.filter(col(CHANGE) != pl.lit("UNCHANGED"))

    return lf


def _parse_date_column(lf: pl.LazyFrame, col_name: str) -> pl.LazyFrame:
    """
    Parse the CMS date field (MM/DD/YYYY string) to a proper Date type.
    Returns the LazyFrame unchanged if the column is absent.
    """
    if col_name not in _lazy_columns(lf):
        return lf
    return lf.with_columns(
        pl.col(col_name)
          .str.strptime(pl.Date, format="%m/%d/%Y", strict=False)
          .alias(col_name)
    )


def _pipe_join_cols(lf: pl.LazyFrame, cols: list[str], out: str) -> pl.LazyFrame:
    """
    Pipe-join multiple string columns into one, skipping nulls and empty strings.
    Returns the LazyFrame with the new column appended.
    """
    present = [c for c in cols if c in _lazy_columns(lf)]
    if not present:
        return lf.with_columns(pl.lit(None).cast(pl.Utf8).alias(out))

    exprs = [
        pl.when(col(c).is_not_null() & (col(c) != "")).then(col(c)).otherwise(None)
        for c in present
    ]
    joined = pl.concat_str(exprs, separator="|", ignore_nulls=True)
    return lf.with_columns(joined.alias(out))


# NODE EXTRACTORS
def _extract_manufacturers(lf: pl.LazyFrame) -> pl.DataFrame:
    schema = _lazy_columns(lf)
    keep = _present([MFR_ID, MFR_NAME, MFR_ST, MFR_COUNTRY, MFR_SUB], schema)
    if MFR_ID not in keep:
        return pl.DataFrame()

    return (
        lf.select(keep)
          .filter(col(MFR_ID).is_not_null() & (col(MFR_ID) != ""))
          .unique(subset=[MFR_ID])
          .rename({k: v for k, v in {
              MFR_ID: "id",
              MFR_NAME: "name",
              MFR_ST: "state",
              MFR_COUNTRY: "country",
              MFR_SUB: "submitting_name",
          }.items() if k in keep}).with_columns([
              pl.lit("Manufacturer").alias("node_type"),
              pl.lit(None).cast(pl.Utf8).alias("specialty"),
              pl.lit(None).cast(pl.Utf8).alias("specialties"),
              pl.lit(None).cast(pl.Utf8).alias("city"),
              pl.lit(None).cast(pl.Utf8).alias("zip_code"),
          ]).collect()
    )


def _extract_physicians(lf: pl.LazyFrame, npi_col: str = NPI) -> pl.DataFrame:
    """
    Extract physician / NPP node records.
    Captures all available specialty slots (1-6), credential type,
    zip code, country, and CMS Profile ID.
    """
    schema = _lazy_columns(lf)
    if npi_col not in schema:
        return pl.DataFrame()

    base_cols = _present([
        npi_col, PROFILE_ID, RCPT_TYPE,
        FNAME, MNAME, LNAME, SUFFIX, CRED1,
        RCPT_ST, RCPT_CTY, RCPT_ZIP, RCPT_CTRY,
    ], schema)

    spec_present = _present(SPEC_COLS, schema)

    # Determine primary specialty: first non-null across slots
    lf_sel = lf.select(base_cols + spec_present)

    # Join all specialty slots into pipe-separated string
    lf_sel = _pipe_join_cols(lf_sel, spec_present, "specialties")

    # Primary specialty = first available slot
    if spec_present:
        primary_spec_expr = pl.coalesce([
            pl.when((col(c).is_not_null()) & (col(c) != "")).then(col(c)).otherwise(None)
            for c in spec_present
        ])
        lf_sel = lf_sel.with_columns(primary_spec_expr.alias("specialty"))
    else:
        lf_sel = lf_sel.with_columns(pl.lit(None).cast(pl.Utf8).alias("specialty"))

    rename_map = {
        npi_col: "id",
        PROFILE_ID: "profile_id",
        RCPT_TYPE: "recipient_type",
        FNAME: "first_name",
        MNAME: "middle_name",
        LNAME: "last_name",
        SUFFIX: "name_suffix",
        CRED1: "credential_type",
        RCPT_ST: "state",
        RCPT_CTY: "city",
        RCPT_ZIP: "zip_code",
        RCPT_CTRY: "country",
    }
    rename_map = {k: v for k, v in rename_map.items() if k in schema}

    # Full name for display
    name_parts = _present([FNAME, LNAME], schema)
    if name_parts:
        lf_sel = lf_sel.with_columns(
            pl.concat_str(
                [pl.col(p) for p in name_parts],
                separator=" ", ignore_nulls=True
            ).alias("name")
        )
    else:
        lf_sel = lf_sel.with_columns(pl.lit(None).cast(pl.Utf8).alias("name"))

    return (
        lf_sel
        .filter(col(npi_col).is_not_null() & (col(npi_col) != ""))
        .unique(subset=[npi_col])
        .rename(rename_map)
        .with_columns(pl.lit("Physician").alias("node_type"))
        .collect()
    )


def _extract_hospitals(lf: pl.LazyFrame) -> pl.DataFrame:
    schema = _lazy_columns(lf)
    if CCN not in schema:
        return pl.DataFrame()

    keep = _present([CCN, HOSP_TH_ID, HOSP_NM, RCPT_ST, RCPT_CTY, RCPT_ZIP, RCPT_CTRY], schema)
    rename_map = {k: v for k, v in {
        CCN: "id",
        HOSP_TH_ID: "hospital_cms_id",
        HOSP_NM: "name",
        RCPT_ST: "state",
        RCPT_CTY: "city",
        RCPT_ZIP: "zip_code",
        RCPT_CTRY: "country",
    }.items() if k in keep}

    return (
        lf.select(keep)
          .filter(col(CCN).is_not_null() & (col(CCN) != ""))
          .unique(subset=[CCN])
          .rename(rename_map)
          .with_columns([
              pl.lit("TeachingHospital").alias("node_type"),
              pl.lit(None).cast(pl.Utf8).alias("specialty"),
              pl.lit(None).cast(pl.Utf8).alias("specialties"),
          ]).collect()
    )


# PRODUCT ASSOCIATION EXTRACTOR
def _extract_products(lf: pl.LazyFrame, record_col: str = RECORD_ID) -> pl.DataFrame:
    """
    Unpack drug/biological (slots 1-5) and device/supply (slots 1-5) product
    names + NDC codes from each payment row into a long-form product table.

    Output schema: record_id, product_type (drug|device), slot,
                   product_name, ndc (null for devices)
    """
    schema = _lazy_columns(lf)
    rows = []

    for i in range(1, N_PRODUCT_SLOTS + 1):
        drug_name_col = f"Name_of_Associated_Covered_Drug_or_Biological_{i}"
        drug_ndc_col = f"NDC_of_Associated_Covered_Drug_or_Biological_{i}"
        dev_name_col = f"Name_of_Associated_Covered_Device_or_Medical_Supply_{i}"
        prod_ind_col = f"Indicate_Drug_or_Biological_or_Device_or_Medical_Supply_{i}"
        prod_name_col = f"Name_of_Drug_or_Biological_or_Device_or_Medical_Supply_{i}"
        prod_ndc_col = f"Associated_Drug_or_Biological_NDC_{i}"

        have_record = record_col in schema

        # Newer combined schema (single name + type indicator)
        if prod_name_col in schema:
            combo_cols = _present([record_col, prod_name_col, prod_ind_col, prod_ndc_col], schema)
            type_expr = (
                pl.when(col(prod_ind_col).str.to_uppercase().str.contains("DRUG|BIO"))
                .then(pl.lit("drug"))
                .when(col(prod_ind_col).str.to_uppercase().str.contains("DEVICE|MEDICAL"))
                .then(pl.lit("device"))
                .otherwise(pl.lit("unknown"))
                if prod_ind_col in combo_cols else pl.lit("unknown")
            )

            df = (
                lf.select(combo_cols)
                  .filter(col(prod_name_col).is_not_null() & (col(prod_name_col) != ""))
                  .with_columns([
                      type_expr.alias("product_type"),
                      pl.lit(i).cast(pl.Int8).alias("slot"),
                      col(prod_name_col).alias("product_name"),
                      (col(prod_ndc_col) if prod_ndc_col in combo_cols else pl.lit(None).cast(pl.Utf8)).alias("ndc"),
                  ]).drop([c for c in [prod_name_col, prod_ind_col, prod_ndc_col] if c in combo_cols]).collect()
            )
            if have_record:
                df = df.rename({record_col: "record_id"})
            rows.append(df)

        # Drugs
        if drug_name_col in schema:
            drug_cols = _present([record_col, drug_name_col, drug_ndc_col], schema)
            df = (
                lf.select(drug_cols)
                  .filter(
                      col(drug_name_col).is_not_null() & (col(drug_name_col) != "")).with_columns([
                          pl.lit("drug").alias("product_type"),
                          pl.lit(i).cast(pl.Int8).alias("slot"),
                          col(drug_name_col).alias("product_name"),
                          (col(drug_ndc_col) if drug_ndc_col in drug_cols else pl.lit(None).cast(pl.Utf8)).alias("ndc"),])
                  .drop([drug_name_col] + ([drug_ndc_col] if drug_ndc_col in drug_cols else []))
                  .collect()
            )
            if have_record:
                df = df.rename({record_col: "record_id"})
            rows.append(df)

        # Devices
        if dev_name_col in schema:
            dev_cols = _present([record_col, dev_name_col], schema)
            df = (
                lf.select(dev_cols)
                  .filter(
                      col(dev_name_col).is_not_null() & (col(dev_name_col) != "")).with_columns([
                          pl.lit("device").alias("product_type"),
                          pl.lit(i).cast(pl.Int8).alias("slot"),
                          col(dev_name_col).alias("product_name"),
                          pl.lit(None).cast(pl.Utf8).alias("ndc"),]).drop([dev_name_col]).collect()
            )
            if have_record:
                df = df.rename({record_col: "record_id"})
            rows.append(df)

    if not rows:
        return pl.DataFrame()

    return (
        pl.concat(rows, how="diagonal")
        .filter(pl.col("product_name").is_not_null())
    )


# EDGE AGGREGATORS
def _agg_general(lf: pl.LazyFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Aggregate General Payment rows into one row per (src, dst, year).

    Returns
    -------
    (edges_df, record_ids_df)
    edges_df: aggregated edges with all financial and flag attributes
    record_ids_df: raw (Record_ID, src_id, dst_id, year) for dedup/incremental
    """
    schema = _lazy_columns(lf)

    needed = [
        RECORD_ID, MFR_ID, NPI, CCN, AMOUNT, PAY_N,
        DATE_PAY, FORM, NATURE, DISPUTE, OWN_IND,
        DELAY, THIRD_PARTY, CHARITY, YEAR_COL, CHANGE,
        # product name cols (for pipe-join on edges)
        *DRUG_NAME_COLS, *DEV_NAME_COLS, *PROD_NAME_COLS,
    ]
    cols_present = _present(needed, schema)
    lf = lf.select(cols_present)

    # Cast numeric / flag columns
    cast_exprs = [
        col(AMOUNT).cast(pl.Float64, strict=False).fill_null(0.0),
        col(YEAR_COL).cast(pl.Int32, strict=False),
        col(PAY_N).cast(pl.Int32, strict=False).fill_null(1).alias("payment_count_raw")
        if PAY_N in cols_present else pl.lit(1).alias("payment_count_raw"),
    ]

    # Boolean flags
    def _bool_col(c: str, alias: str) -> pl.Expr:
        if c in cols_present:
            return col(c).str.to_uppercase().str.contains("YES|Y\\b").cast(pl.Boolean).alias(alias)
        return pl.lit(False).alias(alias)

    def _dispute_col() -> pl.Expr:
        if DISPUTE in cols_present:
            return (
                col(DISPUTE).str.to_uppercase().str.contains("YES|DISPUT")
                .cast(pl.Int32).alias("_disputed")
            )
        return pl.lit(0).alias("_disputed")

    cast_exprs += [
        _bool_col(OWN_IND, "_own"),
        _bool_col(DELAY, "_delay"),
        _bool_col(CHARITY, "_charity"),
        _dispute_col(),
        # third party flag: not "No Third Party"
        (
            ~col(THIRD_PARTY).str.to_uppercase().str.contains("NO THIRD|^NO$|NULL")
            .alias("_third_party")
            if THIRD_PARTY in cols_present else pl.lit(False).alias("_third_party")
        ),
    ]

    lf = lf.with_columns(cast_exprs)

    # Date -> month
    lf = _parse_date_column(lf, DATE_PAY)
    if DATE_PAY in cols_present:
        lf = lf.with_columns(
            col(DATE_PAY).dt.strftime("%Y-%m").alias("payment_month")
        )
    else:
        lf = lf.with_columns(pl.lit(None).cast(pl.Utf8).alias("payment_month"))

    # Pipe-join product names for edge-level product summary
    drug_present = _present(DRUG_NAME_COLS, schema)
    dev_present = _present(DEV_NAME_COLS, schema)
    combo_present = _present(PROD_NAME_COLS, schema)
    lf = _pipe_join_cols(lf, drug_present + dev_present + combo_present, "products")

    frames_edges: list[pl.DataFrame] = []
    frames_rec_ids: list[pl.DataFrame] = []

    def _agg_side(
        lf: pl.LazyFrame,
        dst_col: str,
        dst_type: str,
        extra_filter: pl.Expr | None = None,
    ) -> None:
        if dst_col not in cols_present:
            return
        sub = lf.filter(col(dst_col).is_not_null() & (col(dst_col) != ""))
        if extra_filter is not None:
            sub = sub.filter(extra_filter)

        # Record-level table (for incremental dedup)
        if RECORD_ID in cols_present:
            rec = (
                sub.select(_present([RECORD_ID, MFR_ID, dst_col, YEAR_COL], schema))
                   .rename({
                       RECORD_ID: "record_id",
                       MFR_ID: "src_id",
                       dst_col: "dst_id",
                       YEAR_COL: "year",
                   }).with_columns(pl.lit(dst_type).alias("dst_type")).collect()
            )
            frames_rec_ids.append(rec)

        # Aggregated edge
        edge = (
            sub.group_by([MFR_ID, dst_col, YEAR_COL]).agg([
                                                          col(AMOUNT).sum().alias("total_amount"),
                                                          col("payment_count_raw").sum().alias("payment_count"),
                                                          col(NATURE).drop_nulls().unique().sort().str.join("|").alias("natures")
                                                          if NATURE in cols_present else pl.lit("").alias("natures"),
                                                          col(FORM).drop_nulls().unique().sort().str.join("|").alias("payment_forms")
                                                          if FORM in cols_present else pl.lit("").alias("payment_forms"),
                                                          col("_disputed").sum().alias("disputed_count"),
                                                          col("_own").any().alias("ownership_flag"),
                                                          col("_delay").sum().alias("delay_count"),
                                                          col("_third_party").sum().alias("third_party_count"),
                                                          col("_charity").any().alias("charity_flag"),
                                                          col("payment_month").drop_nulls().unique().sort().str.join("|").alias("active_months"),
                                                          pl.when(col("products").is_not_null() & (col("products") != ""))
                                                          .then(col("products")).otherwise(None)
                                                          .drop_nulls().unique().str.join("|").alias("products")
                                                          if "products" in _lazy_columns(sub) else pl.lit("").alias("products"),]).rename({MFR_ID: "src_id", dst_col: "dst_id", YEAR_COL: "year"}).with_columns(pl.lit(dst_type).alias("dst_type")).collect()
        )
        frames_edges.append(edge)

    # Physician side
    _agg_side(lf, NPI, "Physician")

    # Hospital side (exclude rows that already have a physician NPI)
    hosp_filter = col(NPI).is_null() | (col(NPI) == "") if NPI in cols_present else None
    _agg_side(lf, CCN, "TeachingHospital", extra_filter=hosp_filter)

    edges_df = pl.concat(frames_edges, how="diagonal") if frames_edges else pl.DataFrame()
    rec_ids_df = pl.concat(frames_rec_ids, how="diagonal") if frames_rec_ids else pl.DataFrame()
    return edges_df, rec_ids_df


def _agg_research(lf: pl.LazyFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Aggregate Research Payment rows.

    Produces two edge types:
      - Direct recipient edges (Manufacturer → Physician/Hospital) with
        study_name and clinical_trial_id attached.
      - PI edges (Manufacturer → Principal Investigator) with proportional
        payment splitting across up to 5 PIs.

    Returns
    -------
    (edges_df, pi_nodes_df)
    edges_df     : aggregated research edges
    pi_nodes_df  : physician nodes extracted from PI fields
    """
    schema = _lazy_columns(lf)

    base_cols = _present([
        RECORD_ID, MFR_ID, NPI, CCN, AMOUNT, YEAR_COL, CHANGE,
        DATE_PAY, FORM, NATURE, DISPUTE, DELAY,
        STUDY_NAME, CT_ID, CT_LINK,
        *DRUG_NAME_COLS, *DEV_NAME_COLS,
    ], schema)

    pi_all_cols = _present(
        PI_NPI_COLS + PI_PROF_COLS + PI_FNAME_COLS + PI_LNAME_COLS + PI_CRED_COLS + PI_SPEC_COLS,
        schema,
    )

    lf = lf.select(base_cols + pi_all_cols)
    lf = lf.with_columns([
        col(AMOUNT).cast(pl.Float64, strict=False).fill_null(0.0),
        col(YEAR_COL).cast(pl.Int32, strict=False),
        col(DISPUTE).str.to_uppercase().str.contains("YES|DISPUT")
        .cast(pl.Int32).alias("_disputed")
        if DISPUTE in base_cols else pl.lit(0).alias("_disputed"),
    ])
    lf = _parse_date_column(lf, DATE_PAY)
    lf = _pipe_join_cols(lf, _present(DRUG_NAME_COLS + DEV_NAME_COLS + PROD_NAME_COLS, schema), "products")

    frames: list[pl.DataFrame] = []
    pi_node_frames: list[pl.DataFrame] = []

    def _study_cols_agg(sub: pl.LazyFrame) -> list[pl.Expr]:
        exprs = [
            col(AMOUNT).sum().alias("total_amount"),
            col("_disputed").sum().alias("disputed_count"),
            pl.lit(0).alias("ownership_flag"),
            pl.lit(0).alias("third_party_count"),
            pl.lit(0).alias("charity_flag"),
            pl.lit(0).alias("delay_count"),
        ]
        for c, alias in [(STUDY_NAME, "study_name"), (CT_ID, "clinical_trial_id"),
                         (CT_LINK, "research_info_link"), (NATURE, "natures"),
                         (FORM, "payment_forms"), ("products", "products")]:
            if c in schema or c == "products":
                exprs.append(pl.when(col(c).is_not_null() & (col(c) != "")).then(col(c)).otherwise(None).drop_nulls().unique().str.join("|").alias(alias))
            else:
                exprs.append(pl.lit("").alias(alias))
        return exprs

    # Direct recipient (physician)
    if NPI in schema:
        direct = (
            lf.filter(col(NPI).is_not_null() & (col(NPI) != ""))
              .group_by([MFR_ID, NPI, YEAR_COL])
              .agg(_study_cols_agg(lf))
              .rename({MFR_ID: "src_id", NPI: "dst_id", YEAR_COL: "year"})
              .with_columns([
                  pl.lit("Physician").alias("dst_type"),
                  pl.lit("recipient").alias("edge_subtype"),
              ]).collect()
        )
        frames.append(direct)

    # Direct recipient (hospital)
    if CCN in schema:
        hosp_filter = col(NPI).is_null() | (col(NPI) == "") if NPI in schema else None
        sub = lf.filter(col(CCN).is_not_null() & (col(CCN) != ""))
        if hosp_filter is not None:
            sub = sub.filter(hosp_filter)
        hosp = (
            sub.group_by([MFR_ID, CCN, YEAR_COL]).agg(_study_cols_agg(lf))
                                                 .rename({MFR_ID: "src_id", CCN: "dst_id", YEAR_COL: "year"})
                                                 .with_columns([
                                                               pl.lit("TeachingHospital").alias("dst_type"),
                                                               pl.lit("recipient").alias("edge_subtype"),]).collect()
        )
        frames.append(hosp)

    # PI edges unpivot slots 1–5
    pi_npi_present = _present(PI_NPI_COLS, schema)
    if pi_npi_present:
        pi_count_expr = pl.sum_horizontal(
            [col(c).is_not_null().cast(pl.Int32) for c in pi_npi_present]
        ).clip(lower_bound=1)
        lf_pi = lf.with_columns(
            (col(AMOUNT) / pi_count_expr).alias("_amt_per_pi")
        )

        for i, pi_npi in enumerate(pi_npi_present):
            slot_idx = PI_NPI_COLS.index(pi_npi)

            pi_fname = PI_FNAME_COLS[slot_idx] if slot_idx < len(PI_FNAME_COLS) and PI_FNAME_COLS[slot_idx] in schema else None
            pi_lname = PI_LNAME_COLS[slot_idx] if slot_idx < len(PI_LNAME_COLS) and PI_LNAME_COLS[slot_idx] in schema else None
            pi_cred = PI_CRED_COLS[slot_idx] if slot_idx < len(PI_CRED_COLS) and PI_CRED_COLS[slot_idx] in schema else None
            pi_spec = PI_SPEC_COLS[slot_idx] if slot_idx < len(PI_SPEC_COLS) and PI_SPEC_COLS[slot_idx] in schema else None
            pi_prof = PI_PROF_COLS[slot_idx] if slot_idx < len(PI_PROF_COLS) and PI_PROF_COLS[slot_idx] in schema else None

            # PI nodes
            node_meta_cols = [c for c in [pi_npi, pi_prof, pi_fname, pi_lname, pi_cred, pi_spec] if c]
            if node_meta_cols:
                pi_nodes = (
                    lf_pi.select(node_meta_cols)
                    .filter(col(pi_npi).is_not_null() & (col(pi_npi) != ""))
                    .unique(subset=[pi_npi])
                    .with_columns([
                                  pl.concat_str([col(c) for c in [pi_fname, pi_lname] if c], separator=" ", ignore_nulls=True).alias("name") if any([pi_fname, pi_lname]) else pl.lit(None).cast(pl.Utf8).alias("name"),
                                  pl.lit("Physician").alias("node_type"),]).rename({k: v for k, v in {pi_npi: "id", pi_prof: "profile_id", pi_cred: "credential_type", pi_spec: "specialty", }.items() if k}).collect()
                )
                pi_node_frames.append(pi_nodes)

            # PI edges
            pi_edges = (
                lf_pi.filter(col(pi_npi).is_not_null() & (col(pi_npi) != "")).group_by([MFR_ID, pi_npi, YEAR_COL])
                .agg([
                     col("_amt_per_pi").sum().alias("total_amount"),
                     col("_disputed").sum().alias("disputed_count"),
                     pl.lit(0).alias("ownership_flag"),
                     pl.lit(0).alias("third_party_count"),
                     pl.lit(0).alias("charity_flag"),
                     pl.lit(0).alias("delay_count"),
                     col(STUDY_NAME).drop_nulls().unique().str.join("|").alias("study_name")
                     if STUDY_NAME in schema else pl.lit("").alias("study_name"),
                     col(CT_ID).drop_nulls().unique().str.join("|").alias("clinical_trial_id")
                     if CT_ID in schema else pl.lit("").alias("clinical_trial_id"),
                     col(CT_LINK).drop_nulls().unique().str.join("|").alias("research_info_link")
                     if CT_LINK in schema else pl.lit("").alias("research_info_link"),
                     pl.lit("").alias("natures"),
                     pl.lit("").alias("payment_forms"),
                     pl.lit("").alias("products"),
                     ]).rename({MFR_ID: "src_id", pi_npi: "dst_id", YEAR_COL: "year"})
                       .with_columns([
                                     pl.lit("Physician").alias("dst_type"),
                                     pl.lit("pi").alias("edge_subtype"),]).collect()
            )
            frames.append(pi_edges)

    edges_df = pl.concat(frames, how="diagonal") if frames else pl.DataFrame()
    pi_nodes_df = (
        pl.concat(pi_node_frames, how="diagonal").unique(subset=["id"])
        if pi_node_frames else pl.DataFrame()
    )
    return edges_df, pi_nodes_df


def _agg_ownership(lf: pl.LazyFrame) -> pl.DataFrame:
    """
    Aggregate Physician Ownership Interest records.

    Edge direction: Physician (src) → Manufacturer (dst)
    Added fields: family_member_flag, nature_of_interest
    """
    schema = _lazy_columns(lf)

    needed = [
        RECORD_ID, PHYS_NPI, MFR_ID, OWN_VALUE, OWN_NATURE,
        OWN_FAMILY, YEAR_COL, DISPUTE, CHANGE,
    ]
    cols_present = _present(needed, schema)
    lf = lf.select(cols_present)
    lf = lf.with_columns([
        col(OWN_VALUE).cast(pl.Float64, strict=False).fill_null(0.0)
        if OWN_VALUE in cols_present else pl.lit(0.0),
        col(YEAR_COL).cast(pl.Int32, strict=False),
    ])

    # Family member flag
    if OWN_FAMILY in cols_present:
        lf = lf.with_columns(
            col(OWN_FAMILY).str.to_uppercase().str.contains("FAMILY")
            .cast(pl.Boolean).alias("family_member_flag")
        )
    else:
        lf = lf.with_columns(pl.lit(False).alias("family_member_flag"))

    if DISPUTE in cols_present:
        lf = lf.with_columns(
            col(DISPUTE).str.to_uppercase().str.contains("YES|DISPUT")
            .cast(pl.Int32).alias("_disputed")
        )
    else:
        lf = lf.with_columns(pl.lit(0).alias("_disputed"))

    return (
        lf.filter(col(PHYS_NPI).is_not_null() & (col(PHYS_NPI) != "") if PHYS_NPI in cols_present else pl.lit(True))
          .filter(col(MFR_ID).is_not_null() & (col(MFR_ID) != "") if MFR_ID in cols_present else pl.lit(True))
          .group_by([PHYS_NPI, MFR_ID, YEAR_COL])
          .agg([
              col(OWN_VALUE).sum().alias("total_value")
              if OWN_VALUE in cols_present else pl.lit(0.0).alias("total_value"),
              col(OWN_NATURE).drop_nulls().first().alias("nature_of_interest")
              if OWN_NATURE in cols_present else pl.lit("").alias("nature_of_interest"),
              col("family_member_flag").any().alias("family_member_flag"),
              col("_disputed").sum().alias("disputed_count"),
          ]).rename({PHYS_NPI: "src_id", MFR_ID: "dst_id", YEAR_COL: "year"}).collect()
    )


# ORCHESTRATION
def run(years: list[int] | None = None) -> None:
    target = years or PROGRAM_YEARS
    print(f"GraphLens ETL  |  years: {target}")

    node_frames: list[pl.DataFrame] = []
    general_frames: list[pl.DataFrame] = []
    rec_id_frames: list[pl.DataFrame] = []
    research_frames: list[pl.DataFrame] = []
    own_frames: list[pl.DataFrame] = []
    product_frames: list[pl.DataFrame] = []

    for year in target:
        print(f"\n{year}")

        # General
        gnrl_path = _find_csv(year, "GNRL")
        if gnrl_path:
            print(f"  General   : {gnrl_path.name}")
            gnrl_cols = [
                # Node fields
                MFR_ID, MFR_NAME, MFR_ST, MFR_COUNTRY, MFR_SUB,
                NPI, PROFILE_ID, RCPT_TYPE,
                FNAME, MNAME, LNAME, SUFFIX, CRED1,
                RCPT_ST, RCPT_CTY, RCPT_ZIP, RCPT_CTRY,
                CCN, HOSP_TH_ID, HOSP_NM,
                # Edge core
                RECORD_ID, CHANGE, YEAR_COL, DATE_PAY, AMOUNT, PAY_N,
                FORM, NATURE,
                # Flags
                DISPUTE, OWN_IND, DELAY, THIRD_PARTY, THIRD_NM, CHARITY,
                # Travel
                TRAVEL_CITY, TRAVEL_STATE, TRAVEL_CTRY,
                # Specialties
                *SPEC_COLS,
                # Products
                *DRUG_NAME_COLS, *DRUG_NDC_COLS, *DEV_NAME_COLS,
                *PROD_IND_COLS, *PROD_NAME_COLS, *PROD_NDC_COLS,
            ]
            lf = _read_csv_lazy(gnrl_path, gnrl_cols)

            node_frames += [
                _extract_manufacturers(lf),
                _extract_physicians(lf),
                _extract_hospitals(lf),
            ]

            edges, rec_ids = _agg_general(lf)
            if not edges.is_empty():
                general_frames.append(edges)
            if not rec_ids.is_empty():
                rec_id_frames.append(rec_ids)

            products = _extract_products(lf)
            if not products.is_empty():
                products = products.with_columns(pl.lit(year).cast(pl.Int32).alias("year"))
                product_frames.append(products)
        else:
            print("  General   : NOT FOUND")

        # Research
        rsrch_path = _find_csv(year, "RSRCH")
        if rsrch_path:
            print(f"  Research  : {rsrch_path.name}")
            rsrch_cols = [
                MFR_ID, MFR_NAME, MFR_ST, MFR_COUNTRY,
                NPI, PROFILE_ID, RCPT_TYPE,
                FNAME, LNAME, CRED1, *SPEC_COLS,
                CCN, HOSP_NM,
                RECORD_ID, CHANGE, YEAR_COL, DATE_PAY, AMOUNT,
                FORM, NATURE, DISPUTE, DELAY,
                STUDY_NAME, CT_ID, CT_LINK,
                *DRUG_NAME_COLS, *DEV_NAME_COLS,
                *PROD_IND_COLS, *PROD_NAME_COLS, *PROD_NDC_COLS,
                *PI_NPI_COLS, *PI_PROF_COLS,
                *PI_FNAME_COLS, *PI_LNAME_COLS,
                *PI_CRED_COLS, *PI_SPEC_COLS,
            ]
            lf = _read_csv_lazy(rsrch_path, rsrch_cols)

            node_frames += [
                _extract_manufacturers(lf),
                _extract_physicians(lf),
            ]

            r_edges, pi_nodes = _agg_research(lf)
            if not r_edges.is_empty():
                research_frames.append(r_edges)
            if not pi_nodes.is_empty():
                node_frames.append(pi_nodes)

            products = _extract_products(lf)
            if not products.is_empty():
                products = products.with_columns(pl.lit(year).cast(pl.Int32).alias("year"))
                product_frames.append(products)
        else:
            print("  Research  : NOT FOUND")

        #  Ownership
        own_path = _find_csv(year, "OWNRSHP")
        if own_path:
            print(f"  Ownership : {own_path.name}")
            own_cols = [    # noqa
                RECORD_ID, CHANGE, PHYS_NPI, PHYS_PROF, MFR_ID, MFR_NAME,
                FNAME, LNAME, CRED1, *SPEC_COLS,
                RCPT_ST, OWN_VALUE, OWN_NATURE, OWN_FAMILY,
                YEAR_COL, DISPUTE,
            ]
            df_own = pl.read_csv(own_path, infer_schema=False)
            if CHANGE in df_own.columns:
                df_own = df_own.filter(col(CHANGE) != pl.lit("UNCHANGED"))

            # Also extract physician nodes from ownership file
            lf_own = df_own.lazy()
            node_frames.append(_extract_physicians(lf_own, npi_col=PHYS_NPI))
            node_frames.append(_extract_manufacturers(lf_own))

            agg = _agg_ownership(lf_own)
            if not agg.is_empty():
                own_frames.append(agg)
        else:
            print("  Ownership : NOT FOUND")

    # WRITE PARQUET FILES
    print("\nWriting Parquet files…")

    if node_frames:
        raw_nodes = pl.concat(
            [f for f in node_frames if not f.is_empty()], how="diagonal"
        )
        # Deduplicate: keep the row with the most non-null fields per id
        non_null_count = raw_nodes.with_columns(
            pl.sum_horizontal([
                pl.col(c).is_not_null().cast(pl.Int32)
                for c in raw_nodes.columns
                if c != "id"
            ]).alias("_nn")
        )
        nodes_df = (
            non_null_count
            .sort("_nn", descending=True)
            .unique(subset=["id"], keep="first")
            .drop("_nn")
            .filter(col("id").is_not_null() & (col("id") != ""))
        )
        nodes_df.write_parquet(nodes_path())
        _print_node_summary(nodes_df)

    if general_frames:
        gen_df = (
            pl.concat(general_frames, how="diagonal")
              .group_by(["src_id", "dst_id", "dst_type", "year"])
              .agg([
                  col("total_amount").sum(),
                  col("payment_count").sum(),
                  col("natures").str.join("|").alias("natures"),
                  col("payment_forms").str.join("|").alias("payment_forms"),
                  col("disputed_count").sum(),
                  col("ownership_flag").any(),
                  col("delay_count").sum(),
                  col("third_party_count").sum(),
                  col("charity_flag").any(),
                  col("active_months").str.join("|").alias("active_months"),
                  col("products").str.join("|").alias("products"),
              ])
        )
        gen_df.write_parquet(edges_path())
        print(f"  edges_general.parquet      {len(gen_df):>10,} rows")

    if rec_id_frames:
        rec_df = pl.concat(rec_id_frames, how="diagonal")
        rec_df.write_parquet(record_ids_path())
        print(f"  record_ids_general.parquet {len(rec_df):>10,} rows")

    if research_frames:
        res_df = (
            pl.concat(research_frames, how="diagonal")
              .group_by(["src_id", "dst_id", "dst_type", "year", "edge_subtype"])
              .agg([
                  col("total_amount").sum(),
                  col("disputed_count").sum(),
                  col("study_name").str.join("|").alias("study_name"),
                  col("clinical_trial_id").str.join("|").alias("clinical_trial_id"),
                  col("research_info_link").str.join("|").alias("research_info_link"),
                  col("natures").str.join("|").alias("natures"),
                  col("products").str.join("|").alias("products"),
              ])
        )
        res_df.write_parquet(research_path())
        print(f"  edges_research.parquet     {len(res_df):>10,} rows")

    if own_frames:
        own_df = (
            pl.concat(own_frames, how="diagonal")
              .group_by(["src_id", "dst_id", "year"])
              .agg([
                  col("total_value").sum(),
                  col("nature_of_interest").first(),
                  col("family_member_flag").any(),
                  col("disputed_count").sum(),
              ])
        )
        own_df.write_parquet(ownership_path())
        print(f"  edges_ownership.parquet    {len(own_df):>10,} rows")

    # ---- node_products.parquet ----------------------------------------------
    if product_frames:
        prod_df = (
            pl.concat(product_frames, how="diagonal")
              .filter(col("product_name").is_not_null())
              .unique(subset=["record_id", "product_type", "slot"]) if all("record_id" in f.columns for f in product_frames if not f.is_empty()) else pl.concat(product_frames, how="diagonal")
        )
        prod_df.write_parquet(node_products_path())
        print(f"  node_products.parquet      {len(prod_df):>10,} rows")

    # Summary
    total_mb = sum(p.stat().st_size for p in PROCESSED_DIR.glob("*.parquet")) / 1e6
    print(f"\nDone.  processed/ total size: {total_mb:.1f} MB\n")


def _print_node_summary(nodes_df: pl.DataFrame) -> None:
    n_mfr = (nodes_df["node_type"] == "Manufacturer").sum()
    n_phys = (nodes_df["node_type"] == "Physician").sum()
    n_hosp = (nodes_df["node_type"] == "TeachingHospital").sum()
    print(
        f"  nodes.parquet              {len(nodes_df):>10,} rows  "
        f"({n_mfr:,} mfr  {n_phys:,} phys  {n_hosp:,} hosp)"
    )


# Entry point

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="GraphLens ETL")
    p.add_argument("--year", type=int, default=None, help="Process a single year")
    args = p.parse_args()
    run(years=[args.year] if args.year else None)

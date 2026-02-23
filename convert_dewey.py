#!/usr/bin/env python3
import argparse
import os
import sys
import pandas as pd

# Columns in patterns.csv that our code uses downstream
NEEDED_COLS = [
    'placekey',
    'location_name',
    'poi_cbg',
    'postal_code',
    'median_dwell',
    'popularity_by_hour',
    'popularity_by_day',
    'visitor_daytime_cbgs',
    'visitor_home_cbgs',
    'visits_by_day',
    'bucketed_dwell_times',
    'raw_visit_counts',
    'raw_visitor_counts',
    'related_same_day_brand',
    'related_same_month_brand',
]

# Map common uppercase names to expected lowercase names
RENAME_MAP = {
    'PLACEKEY': 'placekey',
    'PARENT_PLACEKEY': 'parent_placekey',
    'LOCATION_NAME': 'location_name',
    'STREET_ADDRESS': 'street_address',
    'CITY': 'city',
    'REGION': 'region',
    'POSTAL_CODE': 'postal_code',
    'POI_CBG': 'poi_cbg',
    'MEDIAN_DWELL': 'median_dwell',
    'POPULARITY_BY_HOUR': 'popularity_by_hour',
    'POPULARITY_BY_DAY': 'popularity_by_day',
    'VISITOR_DAYTIME_CBGS': 'visitor_daytime_cbgs',
    'VISITOR_HOME_CBGS': 'visitor_home_cbgs',
    'VISITS_BY_DAY': 'visits_by_day',
    'DEVICE_TYPE': 'device_type',
    'SAFEGRAPH_BRAND_IDS': 'safegraph_brand_ids',
    'BRANDS': 'brands',
    'DATE_RANGE_START': 'date_range_start',
    'DATE_RANGE_END': 'date_range_end',
    'RAW_VISIT_COUNTS': 'raw_visit_counts',
    'RAW_VISITOR_COUNTS': 'raw_visitor_counts',
    'RELATED_SAME_DAY_BRAND': 'related_same_day_brand',
    'RELATED_SAME_MONTH_BRAND': 'related_same_month_brand',
}

# JSON-like text columns that sometimes come double-quoted in patterns_n
JSON_TEXT_COLS = [
    'popularity_by_hour',
    'popularity_by_day',
    'visitor_daytime_cbgs',
    'visitor_home_cbgs',
    'visits_by_day',
    'device_type',
    'related_same_day_brand',
    'related_same_month_brand',
    'bucketed_dwell_times',
]


def normalize_json_text(val):
    """Remove outer quotes and unescape where patterns_n stores JSON as a quoted string.
    Returns string (or original if not a string)."""
    if pd.isna(val):
        return val
    if not isinstance(val, str):
        return val
    s = val.strip()
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        s = s[1:-1]
    # Unescape common sequences (e.g., \" -> ")
    s = s.replace('\\"', '"').replace("\\'", "'")
    return s


def convert_date_to_iso(val):
    """Convert date from '2019-01-01 00:00:00.000' to ISO format '2019-01-01T00:00:00-05:00'.
    Assumes US Eastern timezone (-05:00) as default."""
    if pd.isna(val):
        return val
    if not isinstance(val, str):
        return val
    s = val.strip()
    # Already in ISO format with timezone
    if 'T' in s and ('+' in s or s.count('-') >= 3):
        return s
    # Convert from "2019-01-01 00:00:00.000" format
    try:
        # Remove milliseconds if present
        if '.' in s:
            s = s.split('.')[0]
        # Replace space with T and add timezone
        if ' ' in s:
            s = s.replace(' ', 'T') + '-05:00'
        return s
    except Exception:
        return val


def convert_to_int(val):
    """Convert float values to int (e.g., 2479.0 -> 24)."""
    if pd.isna(val):
        return val
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return val


def convert_poi_cbg_to_float_string(val):
    """Convert poi_cbg from int string '400272015104' to float string '400272015104.0'."""
    if pd.isna(val):
        return val
    try:
        # Convert to float to get the .0 suffix
        return float(val)
    except (ValueError, TypeError):
        return val


def process_chunk(df: pd.DataFrame) -> pd.DataFrame:
    # Rename known uppercase columns to expected lowercase names
    cols = {c: RENAME_MAP.get(c, c.lower()) for c in df.columns}
    df = df.rename(columns=cols)

    # Normalize JSON text columns (if present)
    for col in JSON_TEXT_COLS:
        if col in df.columns:
            df[col] = df[col].apply(normalize_json_text)

    # Convert date columns to ISO format with timezone
    if 'date_range_start' in df.columns:
        df['date_range_start'] = df['date_range_start'].apply(convert_date_to_iso)
    if 'date_range_end' in df.columns:
        df['date_range_end'] = df['date_range_end'].apply(convert_date_to_iso)

    # Convert visit counts from float to int (use Int64 to handle NaN while keeping int output)
    if 'raw_visit_counts' in df.columns:
        df['raw_visit_counts'] = pd.to_numeric(df['raw_visit_counts'], errors='coerce').astype('Int64')
    if 'raw_visitor_counts' in df.columns:
        df['raw_visitor_counts'] = pd.to_numeric(df['raw_visitor_counts'], errors='coerce').astype('Int64')

    # Normalize visitor_country_of_origin (unescape JSON)
    if 'visitor_country_of_origin' in df.columns:
        df['visitor_country_of_origin'] = df['visitor_country_of_origin'].apply(normalize_json_text)

    # Enforce numeric types where expected
    # poi_cbg should be float to get the .0 suffix in output
    if 'poi_cbg' in df.columns:
        df['poi_cbg'] = df['poi_cbg'].apply(convert_poi_cbg_to_float_string)
    if 'postal_code' in df.columns:
        df['postal_code'] = pd.to_numeric(df['postal_code'], errors='coerce').astype('Int64')
    if 'median_dwell' in df.columns:
        df['median_dwell'] = pd.to_numeric(df['median_dwell'], errors='coerce')

    return df


def convert(input_csv: str, output_csv: str, only_needed: bool, chunksize: int = 100000):
    first = True
    usecols = None  # read all, then optionally select needed

    # Use the Python engine and be tolerant of occasional bad lines in large vendor CSVs.
    # Also set quote/escape handling for JSON-like columns stored as text.
    # Prefer the C engine for robustness/performance; prior EOF errors were due to in-place overwrite.
    reader = pd.read_csv(
        input_csv,
        chunksize=chunksize,
        engine='c',
    )
    for chunk in reader:
        out = process_chunk(chunk)
        if only_needed:
            keep = [c for c in NEEDED_COLS if c in out.columns]
            # Also keep a few helpful extras if present
            keep += [c for c in ['location_name', 'device_type'] if c in out.columns]
            out = out.loc[:, sorted(set(keep))]
        out.to_csv(output_csv, index=False, mode='w' if first else 'a', header=first)
        first = False


def main():
    ap = argparse.ArgumentParser(description='Convert patterns_n.csv schema to patterns.csv-compatible schema')
    ap.add_argument('--input', '-i', default=os.path.join(os.path.dirname(__file__), '..', 'data', 'patterns_n.csv'),
                    help='Path to patterns_n.csv')
    ap.add_argument('--output', '-o', default=os.path.join(os.path.dirname(__file__), '..', 'data', 'patterns_converted.csv'),
                    help='Output CSV path (defaults to data/patterns_converted.csv)')
    ap.add_argument('--overwrite', action='store_true', help='Write directly to data/patterns.csv')
    ap.add_argument('--only-needed', action='store_true', help='Keep only columns required by downstream code')
    args = ap.parse_args()

    input_csv = os.path.abspath(args.input)
    if args.overwrite:
        output_csv = os.path.join(os.path.dirname(input_csv), 'patterns.csv')
    else:
        output_csv = os.path.abspath(args.output)

    if not os.path.exists(input_csv):
        print(f'Input not found: {input_csv}', file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    # Prevent in-place overwrite while streaming (can corrupt reads). If input and
    # output paths are the same, write to a temporary file then replace.
    same_target = os.path.abspath(input_csv) == os.path.abspath(output_csv)
    tmp_output = output_csv
    if same_target:
        base, ext = os.path.splitext(output_csv)
        tmp_output = f"{base}.tmp{ext or '.csv'}"

    print(f'Converting:\n  from: {input_csv}\n  to:   {tmp_output if same_target else output_csv}\n  only-needed: {args.only_needed}\n')
    convert(input_csv, tmp_output, args.only_needed)

    # Atomic replace if needed
    if same_target:
        os.replace(tmp_output, output_csv)
    print('Done.')


if __name__ == '__main__':
    main()

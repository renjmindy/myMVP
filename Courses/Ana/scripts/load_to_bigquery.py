"""Load parsed Apple Health Parquet tables into BigQuery.

Reads every `records_*.parquet` file produced by `parse_health_export.py` in
the given directory and loads each into its own table in the `apple_health`
dataset, using an explicit schema derived from the DataFrame's dtypes rather
than BigQuery's autodetection (autodetection on load can silently mistype
timestamp columns as strings).

Credentials: set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON key
path before running (do not pass keys as command-line arguments, since those
show up in shell history).
"""

import argparse
import glob
import os

import pandas as pd
from google.cloud import bigquery

DATASET_ID = "apple_health"

_DTYPE_TO_BQ = {
    "object": "STRING",
    "int64": "INTEGER",
    "float64": "FLOAT",
    "bool": "BOOLEAN",
}


def infer_schema(df: pd.DataFrame) -> list[bigquery.SchemaField]:
    fields = []
    for col, dtype in df.dtypes.items():
        if pd.api.types.is_datetime64_any_dtype(dtype):
            bq_type = "TIMESTAMP"
        else:
            bq_type = _DTYPE_TO_BQ.get(str(dtype), "STRING")
        fields.append(bigquery.SchemaField(col, bq_type))
    return fields


def load_parquet_files(client: bigquery.Client, indir: str):
    # Assumes the `apple_health` dataset already exists (created via Console);
    # skip create/get-dataset calls since the loading service account may only
    # have table-level permissions, not bigquery.datasets.get.
    dataset_ref = bigquery.DatasetReference(client.project, DATASET_ID)

    for path in sorted(glob.glob(os.path.join(indir, "records_*.parquet"))):
        table_name = os.path.basename(path).removeprefix("records_").removesuffix(".parquet")
        table_ref = dataset_ref.table(table_name)

        df = pd.read_parquet(path)
        # Timestamps must be UTC for a plain TIMESTAMP column; the source data
        # carries a fixed -07:00 offset, so convert rather than drop it.
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.tz_convert("UTC")

        job_config = bigquery.LoadJobConfig(
            schema=infer_schema(df),
            write_disposition="WRITE_TRUNCATE",
        )
        job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
        job.result()

        table = client.get_table(table_ref)
        print(f"{table_name}: loaded {table.num_rows} rows -> {client.project}.{DATASET_ID}.{table_name}")
        assert table.num_rows == len(df), "row count mismatch after load"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--indir", default="../data", help="Directory containing records_*.parquet files")
    args = parser.parse_args()

    client = bigquery.Client(project=args.project)
    load_parquet_files(client, args.indir)


if __name__ == "__main__":
    main()

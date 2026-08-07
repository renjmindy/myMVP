"""Parse an Apple Health `export.xml` into one Parquet file per HealthKit record type.

Streams the XML with iterparse (constant memory) rather than loading the whole
tree, since a real Apple Health export can run into the gigabytes even though
the sample here is small. Handles `Record`, `Workout`, and `ActivitySummary`
elements generically, so a fuller export can be dropped in later without
changing this script.
"""

import argparse
import os
from collections import defaultdict

import pandas as pd
from lxml import etree

TRACKED_TAGS = {"Record", "Workout", "ActivitySummary"}


def parse_export(xml_path: str) -> dict[str, pd.DataFrame]:
    """Return {healthkit_type: DataFrame} for every element found in xml_path."""
    rows_by_type = defaultdict(list)

    context = etree.iterparse(xml_path, events=("end",), tag=tuple(TRACKED_TAGS))
    for _, elem in context:
        row = dict(elem.attrib)
        metadata = {
            f"metadata_{child.get('key')}": child.get("value")
            for child in elem.findall("MetadataEntry")
        }
        row.update(metadata)

        record_type = row.get("type", elem.tag)
        rows_by_type[record_type].append(row)

        # Free memory for this subtree; safe with iterparse over large files.
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]

    frames = {}
    for record_type, rows in rows_by_type.items():
        df = pd.DataFrame(rows)
        for date_col in ("creationDate", "startDate", "endDate"):
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], utc=False)
        if "value" in df.columns:
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
        frames[record_type] = df

    return frames


def slugify(record_type: str) -> str:
    """HKQuantityTypeIdentifierHeartRate -> heartrate; ActivitySummary -> activitysummary."""
    name = record_type.split("Identifier")[-1] if "Identifier" in record_type else record_type
    return name.lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="../data/export.xml", help="Path to Apple Health export.xml")
    parser.add_argument("--outdir", default="../data", help="Directory to write Parquet files to")
    args = parser.parse_args()

    frames = parse_export(args.input)

    if not frames:
        print("No Record/Workout/ActivitySummary elements found in the export.")
        return

    for record_type, df in frames.items():
        slug = slugify(record_type)
        out_path = os.path.join(args.outdir, f"records_{slug}.parquet")
        df.to_parquet(out_path, index=False)
        print(f"{record_type}: {df.shape[0]} rows, {df.shape[1]} columns -> {out_path}")
        print(df.dtypes.to_string())
        print(df.head(3).to_string())
        print()


if __name__ == "__main__":
    main()

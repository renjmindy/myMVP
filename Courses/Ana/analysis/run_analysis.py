"""Run analysis_queries.sql against BigQuery, save each result as CSV, and
render the daily-trend and hour-of-day charts referenced in report.md.

Usage: python3 run_analysis.py --project ai-map-agent-489008
"""

import argparse
import re
from pathlib import Path

import matplotlib
import pandas as pd
from google.cloud import bigquery

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SQL_PATH = Path(__file__).parent / "queries" / "analysis_queries.sql"
QUERY_TITLE_RE = re.compile(r"^--\s*(\d+)\.\s*(.+)$")


def load_named_queries(sql_path: Path) -> list[tuple[str, str, str]]:
    """Return [(number, title, sql), ...] parsed out of the .sql file."""
    text = sql_path.read_text()
    blocks = re.split(r"\n\n(?=-- \d+\.)", text.strip())

    queries = []
    for block in blocks:
        lines = block.splitlines()
        title_match = None
        sql_lines = []
        for line in lines:
            if title_match is None:
                m = QUERY_TITLE_RE.match(line)
                if m:
                    title_match = m
                    continue
            if not line.strip().startswith("--"):
                sql_lines.append(line)
        if title_match and sql_lines:
            number, title = title_match.groups()
            sql = "\n".join(sql_lines).strip().rstrip(";")
            queries.append((number, title, sql))
    return queries


def run_queries(client: bigquery.Client, outdir: Path) -> dict[str, pd.DataFrame]:
    results = {}
    for number, title, sql in load_named_queries(SQL_PATH):
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
        df = client.query(sql).to_dataframe()
        out_path = outdir / f"query_{number}_{slug}.csv"
        df.to_csv(out_path, index=False)
        print(f"[{number}] {title}: {df.shape[0]} rows -> {out_path.name}")
        results[slug] = df
    return results


def render_charts(results: dict[str, pd.DataFrame], outdir: Path):
    daily = results["daily_summary"]
    hourly = results["hour_of_day_pattern"]

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(daily["day"], daily["avg_hr"], marker="o", label="Daily avg HR")
    ax.set_title("Daily average heart rate (Jan 17-27, 2020)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Heart rate (bpm)")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(outdir / "daily_trend.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(hourly["local_hour"], hourly["avg_hr"], marker="o", color="tab:orange")
    ax.set_title("Average heart rate by hour of day (local time)")
    ax.set_xlabel("Hour of day (0-23)")
    ax.set_ylabel("Heart rate (bpm)")
    ax.set_xticks(range(0, 24, 2))
    fig.tight_layout()
    fig.savefig(outdir / "hourly_pattern.png", dpi=150)
    plt.close(fig)

    print("Saved daily_trend.png and hourly_pattern.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--outdir", default="output", help="Directory to write CSVs/charts to")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    client = bigquery.Client(project=args.project)

    results = run_queries(client, outdir)
    render_charts(results, outdir)


if __name__ == "__main__":
    main()

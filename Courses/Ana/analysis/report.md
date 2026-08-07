# Apple Health Export — Heart Rate Analysis

**Data source:** `data/export.xml` (Apple Health export), parsed via `scripts/parse_health_export.py`, loaded to BigQuery (`ai-map-agent-489008.apple_health.heartrate`) via `scripts/load_to_bigquery.py`, analyzed via `analysis/queries/analysis_queries.sql` / `analysis/run_analysis.py`.

## Assumptions

- **Data scope.** The export contains only `HKQuantityTypeIdentifierHeartRate` records — no `ActiveEnergyBurned`, `Workout`, or `ActivitySummary` data. The original request asked about energy/exercise trends; this report is scoped to heart rate only, since that's all the data supports. The parsing and loading code is written generically and would pick up those record types automatically if a fuller export were supplied.
- **Time range.** 1,000 readings spanning **2020-01-17 to 2020-01-27** (11 calendar days, partial on the first and last day).
- **Timezone.** Every timestamp in the source XML carries a fixed `-07:00` offset. `load_to_bigquery.py` converts to UTC on load; `analysis_queries.sql` reconstructs local time by subtracting 7 hours back off the stored UTC value. No timezone was inferred or guessed — this is exactly the offset present in the source data.
- **Motion context.** Each reading has a `HKMetadataKeyHeartRateMotionContext` value following Apple's enum: `0 = notSet`, `1 = sedentary`, `2 = active`. Used below as a proxy for activity intensity, since no workout/activity data exists to cross-reference against.

## Findings

**1. Heart rate stayed within a narrow, low range throughout.** Across all 1,000 readings, values ranged 58–98 bpm, with a dataset-wide mean around 77–78 bpm. This is consistent with resting/light-activity heart rate; there's no reading suggestive of vigorous exercise.

**2. No statistical outliers.** The outlier query (readings >2 standard deviations from the overall mean) returned **zero rows** — the data is tightly and evenly distributed, with no anomalous spikes or drops.

**3. Day-to-day averages are stable, with no trend.** Daily average HR ranges from 76.0 bpm (Jan 18) to 80.1 bpm (Jan 20), a spread of ~4 bpm. The 3-day rolling average stays flat across the 11-day window — no directional drift up or down (see `daily_trend.png`).

**4. No clear diurnal (day/night) rhythm.** Hour-of-day averages range 74.8–80.1 bpm with no sustained overnight dip (hours 0–5 average ~77–79 bpm, not meaningfully lower than daytime hours) — see `hourly_pattern.png`. Physiologically, resting heart rate typically dips during sleep; its absence here is a data characteristic worth noting, not an inferred health finding.

**5. Motion context barely separates heart rate.** Average HR by motion context: `sedentary` = 77.5 bpm, `active` = 78.6 bpm, `notSet` = 77.3 bpm — about a 1 bpm spread. In this sample, motion context is not a strong differentiator of heart rate intensity, and readings are also fairly evenly split across the three categories (349 / 346 / 305).

**6. Sampling is perfectly regular.** All 999 gaps between consecutive readings are exactly **15 minutes** — a single dominant interval with no variation. This indicates complete, gap-free recording at a fixed cadence, unlike typical opportunistic Apple Watch sensor sampling (which usually shows irregular gaps). This regularity is itself worth flagging (see Data Limitations).

## Recommendations

*The following is general health/fitness guidance, not derived from this dataset — the data here has no exercise, sleep-stage, or long-term trend signal to base personalized recommendations on.*

- A resting heart rate in the high-70s bpm is within the normal adult range, though generally trending toward the higher end of "average" (commonly cited normal resting range: 60–100 bpm, with well-conditioned individuals often lower, in the 50s–60s).
- Regular cardiovascular exercise (e.g., 150+ min/week of moderate activity per common public-health guidance) tends to lower resting heart rate over time as cardiovascular fitness improves.
- If tracking heart rate for fitness or health purposes, capturing `ActiveEnergyBurned` and `Workout` data alongside heart rate would allow much richer analysis (e.g., HR during exercise vs. rest, recovery rate, calorie estimates).
- Anyone concerned about resting heart rate trends, especially sudden changes, should consult a medical professional — this analysis is not a substitute for clinical evaluation.

## Data Limitations

- **Single metric.** Only heart rate is present; no exercise, sleep, or energy-burn data to analyze trends against, despite that being part of the original ask.
- **Short window.** 11 days is too short to assess longer-term trends, weekly patterns, or seasonal effects.
- **Unusually regular sampling.** A perfectly uniform 15-minute gap between all 999 consecutive reading pairs is not typical of real-world Apple Watch heart rate sampling (which is usually irregular/opportunistic). This suggests the sample data may be synthetic or resampled rather than raw sensor output — findings above describe the data as given, not a claim about real-world physiology.
- **No overnight HR dip.** As noted in Finding 4, this is either a genuine feature of the underlying (possibly synthetic) data or an artifact of the fixed-offset timezone assumption; it should not be read as a health signal.

## Artifacts

| File | Contents |
|---|---|
| `query_1_daily_summary.csv` | Daily reading count, avg/min/max/stddev HR, motion-context mix |
| `query_2_hour_of_day_pattern.csv` | Avg/stddev HR by local hour of day |
| `query_3_heart_rate_by_motion_context.csv` | Avg/stddev/min/max HR by motion context |
| `query_4_outlier_detection.csv` | Readings >2σ from the mean (empty — no outliers) |
| `query_5_sampling_consistency_check.csv` | Distribution of gaps between consecutive readings |
| `query_6_day_over_day_trend_3_day_rolling_average_of_the_daily_mean_heart.csv` | Daily avg HR + 3-day rolling average |
| `daily_trend.png` | Chart: daily average HR, Jan 17–27, 2020 |
| `hourly_pattern.png` | Chart: average HR by hour of day |

-- Analysis queries for ai-map-agent-489008.apple_health
--
-- Scope note: the export only contains HKQuantityTypeIdentifierHeartRate
-- records (no ActiveEnergyBurned / Workout / ActivitySummary), so every
-- query here is heart-rate-based. Motion context values follow Apple's
-- HKHeartRateMotionContext enum: 0 = notSet, 1 = sedentary, 2 = active.

-- 1. Daily summary
--    Volume, level, and spread of heart rate per day, plus the mix of
--    motion contexts recorded that day.
SELECT
  DATE(startDate) AS day,
  COUNT(*) AS n_readings,
  ROUND(AVG(value), 1) AS avg_hr,
  MIN(value) AS min_hr,
  MAX(value) AS max_hr,
  ROUND(STDDEV(value), 1) AS stddev_hr,
  ROUND(100 * COUNTIF(metadata_HKMetadataKeyHeartRateMotionContext = '1') / COUNT(*), 1) AS pct_sedentary,
  ROUND(100 * COUNTIF(metadata_HKMetadataKeyHeartRateMotionContext = '2') / COUNT(*), 1) AS pct_active,
  ROUND(100 * COUNTIF(metadata_HKMetadataKeyHeartRateMotionContext = '0') / COUNT(*), 1) AS pct_unset
FROM apple_health.heartrate
GROUP BY day
ORDER BY day;

-- 2. Hour-of-day pattern
--    Local time, reconstructed from the fixed -07:00 source offset, to see
--    the daily rhythm across the whole sample.
SELECT
  EXTRACT(HOUR FROM TIMESTAMP_SUB(startDate, INTERVAL 7 HOUR)) AS local_hour,
  COUNT(*) AS n_readings,
  ROUND(AVG(value), 1) AS avg_hr,
  ROUND(STDDEV(value), 1) AS stddev_hr
FROM apple_health.heartrate
GROUP BY local_hour
ORDER BY local_hour;

-- 3. Heart rate by motion context
--    Checks whether motion context is a usable proxy for activity
--    intensity in this dataset.
SELECT
  metadata_HKMetadataKeyHeartRateMotionContext AS motion_context,
  COUNT(*) AS n_readings,
  ROUND(AVG(value), 1) AS avg_hr,
  ROUND(STDDEV(value), 1) AS stddev_hr,
  MIN(value) AS min_hr,
  MAX(value) AS max_hr
FROM apple_health.heartrate
GROUP BY motion_context
ORDER BY motion_context;

-- 4. Outlier detection
--    Readings more than 2 standard deviations from the overall mean.
WITH stats AS (
  SELECT AVG(value) AS mean_hr, STDDEV(value) AS sd_hr FROM apple_health.heartrate
)
SELECT
  h.startDate,
  h.value,
  h.metadata_HKMetadataKeyHeartRateMotionContext AS motion_context,
  ROUND(s.mean_hr, 1) AS dataset_mean,
  ROUND(s.sd_hr, 1) AS dataset_stddev
FROM apple_health.heartrate h, stats s
WHERE ABS(h.value - s.mean_hr) > 2 * s.sd_hr
ORDER BY h.startDate;

-- 5. Sampling consistency check
--    Distribution of gaps between consecutive readings. A single dominant
--    gap value indicates complete, regular recording with no missing
--    intervals.
WITH ordered AS (
  SELECT
    startDate,
    LEAD(startDate) OVER (ORDER BY startDate) AS next_start
  FROM apple_health.heartrate
)
SELECT
  TIMESTAMP_DIFF(next_start, startDate, MINUTE) AS gap_minutes,
  COUNT(*) AS n_occurrences
FROM ordered
WHERE next_start IS NOT NULL
GROUP BY gap_minutes
ORDER BY n_occurrences DESC;

-- 6. Day-over-day trend: 3-day rolling average of the daily mean heart
--    rate, to check for drift/consistency across the 11-day window.
WITH daily AS (
  SELECT DATE(startDate) AS day, AVG(value) AS avg_hr
  FROM apple_health.heartrate
  GROUP BY day
)
SELECT
  day,
  ROUND(avg_hr, 1) AS avg_hr,
  ROUND(AVG(avg_hr) OVER (ORDER BY day ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS rolling_3day_avg_hr
FROM daily
ORDER BY day;

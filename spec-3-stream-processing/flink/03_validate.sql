-- =============================================================================
-- OPTIONAL CHECKS
-- =============================================================================
-- Unlike Steps 1 and 2, these are separate queries. Run ONE at a time: paste a
-- single query into a cell and click Run. The workspace accepts one statement
-- per run.
--
-- The factory must be running (click Start in the dashboard) so events exist.

-- -----------------------------------------------------------------------------
-- CHECK A (run BEFORE Step 2): can Flink read the raw JSON?
-- Expect 5 rows with job_id, sim_time_ms and occurred_at all filled in.
--   No rows            -> no events yet; start the factory.
--   occurred_at = NULL -> the timestamp conversion in 02_run_jobs.sql needs
--                         adjusting; run SELECT CAST(`val` AS STRING) FROM
--                         `manufacturing-started` LIMIT 1; and check the format.
--   job_id = NULL      -> the JSON path is wrong; look at the raw text as above.
-- -----------------------------------------------------------------------------
SELECT
  JSON_VALUE(CAST(`val` AS STRING), '$.payload.job_id')                AS job_id,
  CAST(JSON_VALUE(CAST(`val` AS STRING), '$.sim_time_ms') AS BIGINT)  AS sim_time_ms,
  CAST(REPLACE(REPLACE(JSON_VALUE(CAST(`val` AS STRING), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at
FROM `manufacturing-started`
LIMIT 5;

-- -----------------------------------------------------------------------------
-- CHECK B (run AFTER Step 2): are results arriving?
-- Rows appear a few seconds after the factory starts.
-- -----------------------------------------------------------------------------
-- SELECT * FROM `job_durations` LIMIT 20;

-- -----------------------------------------------------------------------------
-- CHECK C: the simulated time should equal the planned time.
-- Expect zero rows. Any row returned is a job whose timing looks wrong.
-- -----------------------------------------------------------------------------
-- SELECT job_id, stage, subject, planned_duration_ms, elapsed_sim_ms
-- FROM `job_durations`
-- WHERE elapsed_sim_ms <> planned_duration_ms;

-- -----------------------------------------------------------------------------
-- CHECK D: average duration per stage and station.
-- -----------------------------------------------------------------------------
-- SELECT stage, subject, COUNT(*) AS jobs, AVG(elapsed_sim_ms) AS avg_sim_ms
-- FROM `job_durations`
-- GROUP BY stage, subject;

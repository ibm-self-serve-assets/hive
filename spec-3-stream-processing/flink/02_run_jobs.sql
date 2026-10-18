-- =============================================================================
-- STEP 2 of 2: start the jobs  (run this ONCE, as a single statement)
-- =============================================================================
--
-- WHAT THIS DOES
--   Starts one continuous Flink statement that runs three jobs, one each for
--   gathering, manufacturing and assembly. Each job pairs a "started" event with
--   its "completed" event and writes the time between them to `job_durations`.
--
-- BEFORE YOU RUN
--   * Step 1 (01_create_sink.sql) has been run.
--   * Same workspace context as Step 1 (catalog, database, compute pool).
--   * Paste this whole file into one cell and click Run. The
--     EXECUTE STATEMENT SET ... BEGIN ... END block is what lets several INSERTs
--     run as one statement.
--   * It keeps running until you delete it under "Flink statements". It uses
--     compute pool capacity while running.
--
-- HOW EACH JOB WORKS
--   1. The server publishes plain JSON, so Flink sees `key` and `val` as raw
--      bytes. CAST(`val` AS STRING) turns them into text and JSON_VALUE pulls
--      fields out of it.
--   2. A started event and a completed event belong together when their
--      payload.job_id is equal. Probe events (connection.test) have no job_id,
--      so they never match and are ignored.
--   3. The join only looks for a completed event from 5 seconds before to
--      1 minute after the started event (Kafka record time). Jobs normally
--      take 5-15 s, so this keeps Flink's memory small. A started event with no
--      completed event in that window produces no row.
--      If you slow the simulation down so jobs take over a minute, widen the
--      "+ INTERVAL '1' MINUTE" bound.
--
-- WHAT THE OUTPUT NUMBERS MEAN
--   elapsed_sim_ms  completed.sim_time_ms - started.sim_time_ms. Exact, and
--                   does not depend on simulation speed.
--   elapsed_wall_s  real seconds between the two occurred_at timestamps. Whole
--                   seconds only, and shorter at higher simulation speeds.
--
-- Only values from the events themselves are used (no NOW(), UUID(), RAND()),
-- so replaying the same events gives the same rows.
--
-- Event fields used (see spec-shared/schemas/event_payloads.json):
--   envelope : factory_id, run_id, occurred_at, sim_time_ms
--   payload  : job_id, duration_ms, resource_id / station_id / output_id
-- =============================================================================

EXECUTE STATEMENT SET
BEGIN

-- ---- gathering: gathering-started -> gathering-completed --------------------
INSERT INTO `job_durations`
SELECT
  s.job_id, s.factory_id, s.run_id,
  'gathering'                                         AS stage,
  'gathering-started'                                 AS started_topic,
  'gathering-completed'                               AS completed_topic,
  s.subject, s.output_id,
  s.occurred_at                                       AS started_at,
  c.occurred_at                                       AS completed_at,
  s.planned_duration_ms,
  c.sim_time_ms - s.sim_time_ms                       AS elapsed_sim_ms,
  TIMESTAMPDIFF(SECOND, s.occurred_at, c.occurred_at) AS elapsed_wall_s
FROM (
  SELECT
    JSON_VALUE(CAST(`val` AS STRING), '$.payload.job_id')                        AS job_id,
    JSON_VALUE(CAST(`val` AS STRING), '$.factory_id')                            AS factory_id,
    JSON_VALUE(CAST(`val` AS STRING), '$.run_id')                                AS run_id,
    JSON_VALUE(CAST(`val` AS STRING), '$.payload.resource_id')                   AS subject,
    JSON_VALUE(CAST(`val` AS STRING), '$.payload.resource_id')                   AS output_id,
    CAST(JSON_VALUE(CAST(`val` AS STRING), '$.payload.duration_ms') AS BIGINT)  AS planned_duration_ms,
    CAST(JSON_VALUE(CAST(`val` AS STRING), '$.sim_time_ms') AS BIGINT)          AS sim_time_ms,
    CAST(REPLACE(REPLACE(JSON_VALUE(CAST(`val` AS STRING), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at,
    `$rowtime`                                                                   AS row_time
  FROM `gathering-started`
) AS s
JOIN (
  SELECT
    JSON_VALUE(CAST(`val` AS STRING), '$.payload.job_id')                        AS job_id,
    CAST(JSON_VALUE(CAST(`val` AS STRING), '$.sim_time_ms') AS BIGINT)          AS sim_time_ms,
    CAST(REPLACE(REPLACE(JSON_VALUE(CAST(`val` AS STRING), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at,
    `$rowtime`                                                                   AS row_time
  FROM `gathering-completed`
) AS c
  ON  s.job_id = c.job_id
  AND c.row_time BETWEEN s.row_time - INTERVAL '5' SECOND AND s.row_time + INTERVAL '1' MINUTE;

-- ---- manufacturing: manufacturing-started -> manufacturing-completed --------
INSERT INTO `job_durations`
SELECT
  s.job_id, s.factory_id, s.run_id,
  'manufacturing'                                     AS stage,
  'manufacturing-started'                             AS started_topic,
  'manufacturing-completed'                           AS completed_topic,
  s.subject, s.output_id,
  s.occurred_at                                       AS started_at,
  c.occurred_at                                       AS completed_at,
  s.planned_duration_ms,
  c.sim_time_ms - s.sim_time_ms                       AS elapsed_sim_ms,
  TIMESTAMPDIFF(SECOND, s.occurred_at, c.occurred_at) AS elapsed_wall_s
FROM (
  SELECT
    JSON_VALUE(CAST(`val` AS STRING), '$.payload.job_id')                        AS job_id,
    JSON_VALUE(CAST(`val` AS STRING), '$.factory_id')                            AS factory_id,
    JSON_VALUE(CAST(`val` AS STRING), '$.run_id')                                AS run_id,
    JSON_VALUE(CAST(`val` AS STRING), '$.payload.station_id')                    AS subject,
    JSON_VALUE(CAST(`val` AS STRING), '$.payload.output_id')                     AS output_id,
    CAST(JSON_VALUE(CAST(`val` AS STRING), '$.payload.duration_ms') AS BIGINT)  AS planned_duration_ms,
    CAST(JSON_VALUE(CAST(`val` AS STRING), '$.sim_time_ms') AS BIGINT)          AS sim_time_ms,
    CAST(REPLACE(REPLACE(JSON_VALUE(CAST(`val` AS STRING), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at,
    `$rowtime`                                                                   AS row_time
  FROM `manufacturing-started`
) AS s
JOIN (
  SELECT
    JSON_VALUE(CAST(`val` AS STRING), '$.payload.job_id')                        AS job_id,
    CAST(JSON_VALUE(CAST(`val` AS STRING), '$.sim_time_ms') AS BIGINT)          AS sim_time_ms,
    CAST(REPLACE(REPLACE(JSON_VALUE(CAST(`val` AS STRING), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at,
    `$rowtime`                                                                   AS row_time
  FROM `manufacturing-completed`
) AS c
  ON  s.job_id = c.job_id
  AND c.row_time BETWEEN s.row_time - INTERVAL '5' SECOND AND s.row_time + INTERVAL '1' MINUTE;

-- ---- assembly: assembly-started -> assembly-completed -----------------------
INSERT INTO `job_durations`
SELECT
  s.job_id, s.factory_id, s.run_id,
  'assembly'                                          AS stage,
  'assembly-started'                                  AS started_topic,
  'assembly-completed'                                AS completed_topic,
  s.subject, s.output_id,
  s.occurred_at                                       AS started_at,
  c.occurred_at                                       AS completed_at,
  s.planned_duration_ms,
  c.sim_time_ms - s.sim_time_ms                       AS elapsed_sim_ms,
  TIMESTAMPDIFF(SECOND, s.occurred_at, c.occurred_at) AS elapsed_wall_s
FROM (
  SELECT
    JSON_VALUE(CAST(`val` AS STRING), '$.payload.job_id')                        AS job_id,
    JSON_VALUE(CAST(`val` AS STRING), '$.factory_id')                            AS factory_id,
    JSON_VALUE(CAST(`val` AS STRING), '$.run_id')                                AS run_id,
    JSON_VALUE(CAST(`val` AS STRING), '$.payload.station_id')                    AS subject,
    JSON_VALUE(CAST(`val` AS STRING), '$.payload.output_id')                     AS output_id,
    CAST(JSON_VALUE(CAST(`val` AS STRING), '$.payload.duration_ms') AS BIGINT)  AS planned_duration_ms,
    CAST(JSON_VALUE(CAST(`val` AS STRING), '$.sim_time_ms') AS BIGINT)          AS sim_time_ms,
    CAST(REPLACE(REPLACE(JSON_VALUE(CAST(`val` AS STRING), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at,
    `$rowtime`                                                                   AS row_time
  FROM `assembly-started`
) AS s
JOIN (
  SELECT
    JSON_VALUE(CAST(`val` AS STRING), '$.payload.job_id')                        AS job_id,
    CAST(JSON_VALUE(CAST(`val` AS STRING), '$.sim_time_ms') AS BIGINT)          AS sim_time_ms,
    CAST(REPLACE(REPLACE(JSON_VALUE(CAST(`val` AS STRING), '$.occurred_at'), 'T', ' '), '+00:00', '') AS TIMESTAMP(3)) AS occurred_at,
    `$rowtime`                                                                   AS row_time
  FROM `assembly-completed`
) AS c
  ON  s.job_id = c.job_id
  AND c.row_time BETWEEN s.row_time - INTERVAL '5' SECOND AND s.row_time + INTERVAL '1' MINUTE;

END;

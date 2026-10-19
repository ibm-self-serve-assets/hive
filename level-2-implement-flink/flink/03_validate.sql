-- =============================================================================
-- VALIDATE FLINK OPERATION
-- =============================================================================
-- The factory must be running (click Start in the dashboard) so events exist.
-- -----------------------------------------------------------------------------
-- Are results arriving in job_durations?
-- Rows appear a few seconds after the factory starts and jobs complete.
-- -----------------------------------------------------------------------------
SELECT * FROM `job_durations` LIMIT 20;
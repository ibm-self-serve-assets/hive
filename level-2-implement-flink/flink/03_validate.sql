-- =============================================================================
-- VALIDATE FLINK OPERATION
-- =============================================================================
-- The factory must be running (click Start in the dashboard) so events exist.
-- -----------------------------------------------------------------------------
-- Are results arriving in calculated_values?
-- Rows appear a few seconds after the factory starts and jobs complete.
-- -----------------------------------------------------------------------------
SELECT * FROM `calculated_values` LIMIT 20;
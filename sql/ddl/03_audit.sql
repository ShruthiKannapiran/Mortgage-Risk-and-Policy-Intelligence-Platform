-- Pipeline execution / audit log — one row per pipeline run per stage.
CREATE TABLE IF NOT EXISTS pipeline_execution_log (
    run_id           VARCHAR NOT NULL,
    stage            VARCHAR NOT NULL,   -- ingestion | transformation | dimensional_load | data_quality
    started_at       TIMESTAMP NOT NULL,
    ended_at         TIMESTAMP,
    status           VARCHAR NOT NULL,   -- RUNNING | SUCCESS | FAILED
    rows_read        INTEGER,
    rows_new         INTEGER,
    rows_updated     INTEGER,
    rows_unchanged   INTEGER,
    rows_rejected    INTEGER,
    error_message    VARCHAR,
    PRIMARY KEY (run_id, stage)
);

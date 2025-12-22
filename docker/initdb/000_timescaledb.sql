-- docker/initdb/000_timescaledb.sql
-- Enable TimescaleDB extension (idempotent)

CREATE EXTENSION IF NOT EXISTS timescaledb;

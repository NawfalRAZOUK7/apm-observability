\echo '--- Verify Timescale extension'
SELECT extname FROM pg_extension WHERE extname = 'timescaledb';

\echo '--- List existing hypertables'
SELECT hypertable_schema, hypertable_name, num_dimensions, num_chunks, compression_enabled
FROM timescaledb_information.hypertables
ORDER BY hypertable_schema, hypertable_name;

\echo '--- Demo table setup (drop/create)'
DROP TABLE IF EXISTS demo_requests;
CREATE TABLE demo_requests (
  time timestamptz NOT NULL,
  service text NOT NULL,
  latency_ms integer NOT NULL
);
SELECT create_hypertable('demo_requests', 'time', if_not_exists => true);

\echo '--- Insert sample rows'
INSERT INTO demo_requests (time, service, latency_ms) VALUES
  (now() - interval '5 min', 'api', 120),
  (now() - interval '4 min', 'api', 90),
  (now() - interval '3 min', 'billing', 210),
  (now() - interval '2 min', 'api', 150),
  (now() - interval '1 min', 'billing', 110);

\echo '--- time_bucket aggregate (1 minute)'
SELECT
  time_bucket('1 minute', time) AS bucket,
  service,
  count(*) AS hits,
  avg(latency_ms) AS avg_latency_ms
FROM demo_requests
GROUP BY bucket, service
ORDER BY bucket DESC, service;

\echo '--- Hypertable info for demo_requests'
SELECT *
FROM timescaledb_information.hypertables
WHERE hypertable_name = 'demo_requests';

\echo '--- Chunk info for demo_requests'
SELECT chunk_schema, chunk_name, range_start, range_end
FROM timescaledb_information.chunks
WHERE hypertable_name = 'demo_requests'
ORDER BY range_start;

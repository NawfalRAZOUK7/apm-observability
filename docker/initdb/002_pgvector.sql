-- docker/initdb/002_pgvector.sql
-- Enable pgvector extension (idempotent)

CREATE EXTENSION IF NOT EXISTS vector;

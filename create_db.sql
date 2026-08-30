-- Run as: sudo -u postgres psql -f create_db.sql
-- sudo -u postgres psql < create_db.sql # INCASE CMD ABOVE FAILS
--
-- Creates the "serial-gateway-program" database and the two tables the
-- gateway listener code reads/writes: node_database and filter_time_py.
-- Column names/types are taken directly from the queries in
-- database_aligner.py, database_thread.py, and gps_database_thread.py.

CREATE DATABASE "serial-gateway-program" OWNER pi;

\c "serial-gateway-program"

-- node_database: one row per node (plus the 2 gateway nodes themselves).
-- Only "node" is required NOT NULL - a freshly-registered node has no
-- GPS fix yet, so latitude/longitude/description start out NULL and get
-- filled in later by GPSDatabaseThread.
CREATE TABLE node_database (
    id          SERIAL PRIMARY KEY,
    pole_node   TEXT,
    node        TEXT NOT NULL,
    pan_id      TEXT,
    channel     TEXT,
    latitude    TEXT,
    longitude   TEXT,
    description TEXT
);

-- Indexes matching the code's actual query patterns
-- (every lookup is "where node = %s" or "where pan_id = %s and channel = %s")
CREATE INDEX idx_node_database_node ON node_database (node);
CREATE INDEX idx_node_database_pan_channel ON node_database (pan_id, channel);

-- filter_time_py: message-ID/timestamp tracking per (node, ack-label) pair.
-- dtime must be TIMESTAMP (not TIMESTAMPTZ) - the code compares it
-- directly against naive datetime.utcnow() values, which raises a
-- TypeError against a timezone-aware column.
-- dec_count/rollover_count/miss_count need DEFAULT 0: the initial INSERT
-- (see database_thread.py) never sets them, but later code does
-- int(row[...]) on them unconditionally.
CREATE TABLE filter_time_py (
    id              SERIAL PRIMARY KEY,
    node            TEXT NOT NULL,
    ack             TEXT NOT NULL,
    dtime           TIMESTAMP,
    msgid           TEXT,
    oo_msgid        TEXT,
    dec_count       INTEGER DEFAULT 0,
    rollover_count  INTEGER DEFAULT 0,
    miss_count      INTEGER DEFAULT 0,
    override_flag   BOOLEAN,
    lamp_status     BOOLEAN
);

CREATE INDEX idx_filter_time_py_node_ack ON filter_time_py (node, ack);

-- Table/sequence-level privileges for the pi role.
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pi;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pi;
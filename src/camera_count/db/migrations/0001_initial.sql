-- Camera Count Tool - initial schema.
--
-- The rule the rest of the program enforces in types is enforced here in
-- constraints: a row may only carry a count when it also carries the source
-- that produced it. A reading with a value and no source cannot be stored.

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER NOT NULL,
    applied_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS inspections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at_utc  TEXT    NOT NULL,
    started_at_local TEXT   NOT NULL,
    app_version     TEXT    NOT NULL,
    git_hash        TEXT,
    mode            TEXT    NOT NULL CHECK (mode IN ('camera', 'image')),
    manufacturer    TEXT,
    model           TEXT,
    serial          TEXT,
    firmware        TEXT,
    protocol        TEXT,
    usb_vendor_id   INTEGER,
    usb_product_id  INTEGER,
    usb_interfaces  TEXT,
    adapter         TEXT,
    registry_model  TEXT,
    headline        TEXT    NOT NULL,
    exact_count_found INTEGER NOT NULL CHECK (exact_count_found IN (0, 1)),
    seller_notes    TEXT,
    buyer_notes     TEXT
);

CREATE TABLE IF NOT EXISTS shutter_readings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id   INTEGER NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    count_type      TEXT    NOT NULL CHECK (
                        count_type IN ('mechanical', 'electronic', 'efc', 'total_releases')
                    ),
    available       INTEGER NOT NULL CHECK (available IN (0, 1)),
    value           INTEGER CHECK (value IS NULL OR value >= 0),
    source_id       TEXT,
    method_type     TEXT,
    identifier      TEXT,
    verification_status TEXT CHECK (
                        verification_status IS NULL
                        OR verification_status IN ('documented', 'hardware_verified')
                    ),
    citation        TEXT,
    transaction_ref TEXT,
    message         TEXT,
    reason          TEXT,
    -- A value may exist only together with a trusted, cited source.
    CHECK (
        (available = 1
         AND value IS NOT NULL
         AND source_id IS NOT NULL
         AND citation IS NOT NULL
         AND verification_status IS NOT NULL)
        OR
        (available = 0 AND value IS NULL AND reason IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS non_authoritative_counters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id   INTEGER NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    label           TEXT    NOT NULL,
    value           TEXT    NOT NULL,
    origin          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS images (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id   INTEGER NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    path            TEXT    NOT NULL,
    file_name       TEXT    NOT NULL,
    size_bytes      INTEGER NOT NULL,
    sha256          TEXT    NOT NULL,
    file_type       TEXT,
    capture_date    TEXT,
    is_original     INTEGER NOT NULL CHECK (is_original IN (0, 1)),
    originality_reason TEXT,
    raw_metadata    TEXT
);

CREATE TABLE IF NOT EXISTS protocol_transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id   INTEGER NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    reference       TEXT    NOT NULL,
    sequence        INTEGER NOT NULL,
    timestamp_utc   TEXT    NOT NULL,
    transport       TEXT    NOT NULL,
    operation       TEXT    NOT NULL,
    opcode          INTEGER NOT NULL,
    parameters      TEXT,
    response_name   TEXT,
    response_code   INTEGER,
    data_hex        TEXT,
    duration_ms     REAL,
    note            TEXT
);

CREATE TABLE IF NOT EXISTS verification_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer    TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    firmware        TEXT,
    source_id       TEXT    NOT NULL,
    reading_before  INTEGER NOT NULL,
    presses         INTEGER NOT NULL CHECK (presses > 0),
    reading_after   INTEGER NOT NULL,
    matched         INTEGER NOT NULL CHECK (matched IN (0, 1)),
    tested_at       TEXT    NOT NULL,
    tester          TEXT,
    notes           TEXT,
    -- The whole point of the test: after - before must equal the presses made.
    CHECK ((matched = 1 AND reading_after - reading_before = presses)
           OR matched = 0)
);

CREATE INDEX IF NOT EXISTS idx_readings_inspection ON shutter_readings(inspection_id);
CREATE INDEX IF NOT EXISTS idx_images_inspection ON images(inspection_id);
CREATE INDEX IF NOT EXISTS idx_transactions_inspection ON protocol_transactions(inspection_id);
CREATE INDEX IF NOT EXISTS idx_inspections_started ON inspections(started_at_utc);

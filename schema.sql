-- ============================================================
-- ERP Workflow Extension Prototype — Schema
-- Simulates EFACS-style ERP extensions for manufacturing
-- ============================================================

PRAGMA foreign_keys = ON;

-- ─── SUPPLIERS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS suppliers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    contact     TEXT,
    email       TEXT,
    phone       TEXT,
    lead_days   INTEGER DEFAULT 7,
    status      TEXT DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','SUSPENDED','PENDING')),
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ─── STOCK / PARTS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS parts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    part_number     TEXT NOT NULL UNIQUE,
    description     TEXT NOT NULL,
    category        TEXT,
    unit_cost       REAL NOT NULL,
    qty_on_hand     INTEGER DEFAULT 0,
    qty_reserved    INTEGER DEFAULT 0,
    reorder_point   INTEGER DEFAULT 10,
    unit_of_measure TEXT DEFAULT 'EA',
    supplier_id     INTEGER REFERENCES suppliers(id)
);

-- ─── PURCHASE ORDERS ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS purchase_orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number       TEXT NOT NULL UNIQUE,
    supplier_id     INTEGER NOT NULL REFERENCES suppliers(id),
    raised_by       TEXT NOT NULL,
    raised_date     TEXT DEFAULT (date('now')),
    required_date   TEXT,
    total_value     REAL DEFAULT 0,
    status          TEXT DEFAULT 'DRAFT'
                    CHECK(status IN ('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','SENT','RECEIVED','CANCELLED')),
    approval_note   TEXT,
    approved_by     TEXT,
    approved_at     TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ─── PO LINE ITEMS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS po_lines (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id       INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    part_id     INTEGER NOT NULL REFERENCES parts(id),
    qty_ordered INTEGER NOT NULL,
    unit_price  REAL NOT NULL,
    line_total  REAL GENERATED ALWAYS AS (qty_ordered * unit_price) STORED
);

-- ─── STOCK RESERVATIONS ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS reservations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id         INTEGER NOT NULL REFERENCES parts(id),
    qty_reserved    INTEGER NOT NULL,
    reserved_for    TEXT NOT NULL,   -- e.g. work order or project ref
    reserved_by     TEXT NOT NULL,
    status          TEXT DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','FULFILLED','CANCELLED')),
    reservation_date TEXT DEFAULT (date('now')),
    notes           TEXT
);

-- ─── INVOICES ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invoices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number  TEXT NOT NULL UNIQUE,
    po_id           INTEGER REFERENCES purchase_orders(id),
    supplier_id     INTEGER NOT NULL REFERENCES suppliers(id),
    invoice_date    TEXT NOT NULL,
    due_date        TEXT,
    amount          REAL NOT NULL,
    status          TEXT DEFAULT 'PENDING'
                    CHECK(status IN ('PENDING','VALIDATED','APPROVED','DISPUTED','PAID')),
    validation_note TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ─── WORKFLOW AUDIT LOG ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS workflow_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,   -- 'PO', 'RESERVATION', 'INVOICE'
    entity_id   INTEGER NOT NULL,
    action      TEXT NOT NULL,
    performed_by TEXT NOT NULL,
    note        TEXT,
    logged_at   TEXT DEFAULT (datetime('now'))
);

-- ─── SEED DATA ───────────────────────────────────────────────
INSERT OR IGNORE INTO suppliers (code, name, contact, email, phone, lead_days, status) VALUES
    ('SUP001', 'Precision Metals Ltd',     'Alan Shaw',    'a.shaw@precisionmetals.co.uk',   '0161 400 1100', 5,  'ACTIVE'),
    ('SUP002', 'HydraFlex Components',     'Sara Okonkwo', 's.okonkwo@hydraflex.co.uk',      '0121 700 2200', 10, 'ACTIVE'),
    ('SUP003', 'Northern Fasteners Co.',   'James Birch',  'j.birch@nfasteners.co.uk',       '0113 500 3300', 3,  'ACTIVE'),
    ('SUP004', 'Confined Space Seals Ltd', 'Priya Nair',   'p.nair@csseals.co.uk',           '0151 600 4400', 14, 'SUSPENDED');

INSERT OR IGNORE INTO parts (part_number, description, category, unit_cost, qty_on_hand, qty_reserved, reorder_point, supplier_id) VALUES
    ('PM-0041',  'Stainless Steel Shaft 40mm',        'Raw Material',  18.50, 42, 5,  15, 1),
    ('PM-0082',  'Aluminium Bracket Type-B',           'Raw Material',  11.20, 8,  3,  20, 1),
    ('HF-1120',  'Hydraulic Seal Kit 1-1/4"',          'Components',    34.00, 25, 0,  10, 2),
    ('HF-2240',  'Pressure Relief Valve PRV-224',      'Components',   120.00, 4,  4,  5,  2),
    ('NF-0010',  'M10 Hex Bolt Grade 8.8 (Box 100)',   'Fasteners',     14.75, 60, 0,  30, 3),
    ('NF-0016',  'M16 Flange Nut A2 SS (Box 50)',      'Fasteners',     22.00, 15, 5,  20, 3),
    ('CS-3310',  'PTFE Rod Seal 33mm',                 'Seals',         47.50, 3,  2,  8,  4);

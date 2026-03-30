# ERP Workflow Extension Prototype

> **A lightweight, form-driven ERP module** simulating the screen logic, business rule validation, and workflow triggers found in systems like EFACS (Exel). Built as a portfolio demonstration of ERP extension development patterns for a manufacturing/engineering context.

---

## Overview

This prototype replicates the kind of work done when extending a vendor ERP system — building custom screens, enforcing business rules without touching core vendor code, creating SQL-driven reports, and implementing multi-step approval workflows. It targets the exact patterns used in **EFACS by Exel** for precision engineering environments.

**Stack:** Python · Flask · SQLite · Jinja2 · Vanilla JS

---

## Modules Implemented

### 1. Purchase Order Approval Workflow
- Create POs with dynamic line items and live order totals
- **Business Rule:** POs ≤ £500 are auto-approved on submission; POs above threshold route to manager review
- Role-based approval: only users with `can_approve` permission can approve/reject
- Full rejection reason capture and audit trail
- PO status lifecycle: `DRAFT → PENDING_APPROVAL → APPROVED/REJECTED → SENT → RECEIVED`

### 2. Stock Reservation with Availability Check
- Parts register with live available qty = `qty_on_hand − qty_reserved`
- **Business Rule:** Reservation blocked server-side if requested quantity exceeds available stock
- Reservations reduce available stock immediately; cancellation releases it
- Visual stock status: `OK / LOW STOCK / OUT OF STOCK` based on reorder points

### 3. Supplier Management
- Supplier register with status lifecycle (`ACTIVE / SUSPENDED / PENDING`)
- **Business Rule:** Suspended suppliers excluded from PO creation dropdowns
- Lead time captured per supplier and surfaced in PO form as a screen hint

### 4. Invoice Validation (3-Way Match)
- Invoices linked to approved POs
- **Business Rule:** Automatic 3-way match on save — if invoice amount differs from PO value by more than 2%, invoice is flagged `DISPUTED`; within tolerance → `VALIDATED`
- Live match preview in form before submission
- Approval workflow for validated invoices

### 5. SQL Reporting (BIRT-Style)
- Procurement spend by supplier (aggregation with `COUNT`, `SUM`, `AVG`)
- Purchase order status summary
- Invoice aging report (using `julianday()` to simulate SQL Server `DATEDIFF`)
- Stock health report with `CASE` expression for status classification
- SQL shown inline below each table — mirrors BIRT dataset transparency

### 6. Workflow Audit Log
- Every state change (create, submit, approve, reject, reserve, cancel) written to `workflow_log`
- Immutable record: entity type, entity ID, action, user, timestamp, and note
- Displayed on dashboard and on individual PO detail views

---

## ERP Extension Patterns Demonstrated

| Pattern | Where Demonstrated |
|---|---|
| Custom screen with form logic | PO form (dynamic line items, live total, approval flag) |
| Business rule enforcement | PO threshold, stock availability check, 3-way match |
| Workflow state machine | PO lifecycle (DRAFT → APPROVED/REJECTED) |
| Role-based action gating | Approval buttons shown/hidden by user role |
| Audit trail / event log | `workflow_log` table, surfaced on dashboard and detail views |
| SQL aggregation reporting | Reports page — spend, status summary, aging, stock health |
| Vendor extension without core modification | All logic in application layer; schema is additive |
| Lead time / supplier data surfaced in UI | Supplier lead days shown as hint in PO form |

---

## Database Schema

```
suppliers       → code, name, contact, status, lead_days
parts           → part_number, qty_on_hand, qty_reserved, reorder_point
purchase_orders → po_number, supplier_id, status, total_value, approval fields
po_lines        → po_id, part_id, qty_ordered, unit_price, line_total (generated)
reservations    → part_id, qty_reserved, reserved_for, status
invoices        → invoice_number, po_id, amount, status, validation_note
workflow_log    → entity_type, entity_id, action, performed_by, note, logged_at
```

---

## Getting Started

```bash
# Clone and install
git clone https://github.com/Nivedita-Saha/erp-workflow-prototype.git
cd erp-workflow-prototype
pip install -r requirements.txt

# Run (database auto-initialises with seed data on first run)
python app.py
```

Open `http://localhost:5050` — select a demo user to log in:

| Username | Role | Can Approve? |
|---|---|---|
| `niv` | Developer | Yes |
| `manager` | Manager | Yes |
| `buyer` | Buyer | No |

---

## Project Structure

```
erp-workflow-prototype/
├── app.py                  # Flask app, routes, business logic
├── schema.sql              # DB schema + seed data
├── requirements.txt
├── instance/
│   └── erp.db              # SQLite DB (auto-created)
├── templates/
│   ├── base.html           # Sidebar layout
│   ├── login.html
│   ├── dashboard.html      # KPI stats + audit log
│   ├── po_list.html        # Purchase order list
│   ├── po_form.html        # PO creation with line item builder
│   ├── po_detail.html      # PO view + approval panel
│   ├── stock.html          # Parts register
│   ├── reserve_form.html   # Stock reservation
│   ├── reservations.html   # Active reservations
│   ├── suppliers.html      # Supplier register
│   ├── supplier_form.html  # New supplier
│   ├── invoices.html       # Invoice register
│   ├── invoice_form.html   # Log invoice + 3-way match preview
│   └── reports.html        # SQL reports dashboard
└── static/
    ├── css/style.css
    └── js/main.js
```

---

## Relevance to EFACS / ERP Development

This prototype is designed to demonstrate understanding of:

- **EFACS screen extensions** — form logic, field validation, conditional UI (approval panel shown/hidden by role and status)
- **BIRT report development** — each report table shows the underlying SQL, uses aggregations, CTEs, and CASE expressions
- **Workflow triggers** — state transitions fire audit log entries, mirror EFACS workflow configuration
- **SQL Server patterns** — queries use joins, aggregations, CASE expressions, and date arithmetic consistent with SQL Server syntax
- **Extending without modifying core** — all logic sits in the application/extension layer; the schema only adds tables

---

*Built by Nivedita Saha · MSc Artificial Intelligence & Data Science (Distinction) · Keele University 2025*

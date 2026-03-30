"""
ERP Workflow Extension Prototype
=================================
Simulates EFACS-style ERP extension patterns:
  - Custom screen/form logic
  - Business rule validation
  - Multi-step workflow triggers
  - SQL-driven reporting (BIRT-style)

Stack: Python/Flask + SQLite
"""

import os
import sqlite3
from datetime import date, datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, g, jsonify, session)

# ─── App Setup ────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "erp-dev-secret-2025")

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "erp.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

# Simulated user session (in production: proper auth)
USERS = {
    "niv":     {"name": "Nivedita Saha",   "role": "developer",  "can_approve": True},
    "manager": {"name": "James Holroyd",   "role": "manager",    "can_approve": True},
    "buyer":   {"name": "Rachel Osei",     "role": "buyer",      "can_approve": False},
}

# ─── Database Helpers ─────────────────────────────────────────
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()

def query(sql, params=(), one=False):
    cur = get_db().execute(sql, params)
    result = cur.fetchone() if one else cur.fetchall()
    return result

def execute(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur.lastrowid

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        with open(SCHEMA_PATH) as f:
            conn.executescript(f.read())
        conn.close()

# ─── Auth Helper ──────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def current_user():
    return USERS.get(session.get("user"), {})

# ─── Business Rules ───────────────────────────────────────────
PO_APPROVAL_THRESHOLD = 500.00   # POs above this need manager approval

def calculate_po_total(po_id):
    result = query("SELECT SUM(line_total) as t FROM po_lines WHERE po_id=?", (po_id,), one=True)
    return result["t"] or 0.0

def check_stock_availability(part_id, qty_needed):
    part = query("SELECT qty_on_hand, qty_reserved FROM parts WHERE id=?", (part_id,), one=True)
    if not part:
        return False, 0
    available = part["qty_on_hand"] - part["qty_reserved"]
    return available >= qty_needed, available

def log_workflow(entity_type, entity_id, action, note=""):
    user = current_user().get("name", "System")
    execute(
        "INSERT INTO workflow_log (entity_type, entity_id, action, performed_by, note) VALUES (?,?,?,?,?)",
        (entity_type, entity_id, action, user, note)
    )

# ─── Auth Routes ──────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").lower()
        if username in USERS:
            session["user"] = username
            flash(f"Welcome back, {USERS[username]['name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─── Dashboard ────────────────────────────────────────────────
@app.route("/")
@login_required
def dashboard():
    stats = {
        "po_pending":    query("SELECT COUNT(*) as c FROM purchase_orders WHERE status='PENDING_APPROVAL'", one=True)["c"],
        "po_draft":      query("SELECT COUNT(*) as c FROM purchase_orders WHERE status='DRAFT'", one=True)["c"],
        "low_stock":     query("SELECT COUNT(*) as c FROM parts WHERE (qty_on_hand - qty_reserved) <= reorder_point", one=True)["c"],
        "inv_pending":   query("SELECT COUNT(*) as c FROM invoices WHERE status='PENDING'", one=True)["c"],
        "inv_disputed":  query("SELECT COUNT(*) as c FROM invoices WHERE status='DISPUTED'", one=True)["c"],
        "reservations":  query("SELECT COUNT(*) as c FROM reservations WHERE status='ACTIVE'", one=True)["c"],
    }
    recent_log = query(
        "SELECT * FROM workflow_log ORDER BY logged_at DESC LIMIT 8"
    )
    pending_pos = query(
        """SELECT po.*, s.name as supplier_name FROM purchase_orders po
           JOIN suppliers s ON po.supplier_id = s.id
           WHERE po.status = 'PENDING_APPROVAL' ORDER BY po.created_at DESC LIMIT 5"""
    )
    return render_template("dashboard.html", stats=stats, recent_log=recent_log,
                           pending_pos=pending_pos, user=current_user())

# ─── SUPPLIERS ────────────────────────────────────────────────
@app.route("/suppliers")
@login_required
def suppliers():
    rows = query("SELECT * FROM suppliers ORDER BY name")
    return render_template("suppliers.html", suppliers=rows, user=current_user())

@app.route("/suppliers/new", methods=["GET", "POST"])
@login_required
def new_supplier():
    if request.method == "POST":
        code    = request.form["code"].upper().strip()
        name    = request.form["name"].strip()
        contact = request.form.get("contact", "")
        email   = request.form.get("email", "")
        phone   = request.form.get("phone", "")
        lead    = int(request.form.get("lead_days", 7))

        # Validation
        if not code or not name:
            flash("Supplier code and name are required.", "error")
            return render_template("supplier_form.html", user=current_user(), supplier=request.form)
        existing = query("SELECT id FROM suppliers WHERE code=?", (code,), one=True)
        if existing:
            flash(f"Supplier code {code} already exists.", "error")
            return render_template("supplier_form.html", user=current_user(), supplier=request.form)

        sid = execute(
            "INSERT INTO suppliers (code, name, contact, email, phone, lead_days) VALUES (?,?,?,?,?,?)",
            (code, name, contact, email, phone, lead)
        )
        log_workflow("SUPPLIER", sid, "CREATED", f"New supplier {code} — {name}")
        flash(f"Supplier {code} created successfully.", "success")
        return redirect(url_for("suppliers"))
    return render_template("supplier_form.html", user=current_user(), supplier={})

@app.route("/suppliers/<int:sid>/toggle", methods=["POST"])
@login_required
def toggle_supplier(sid):
    sup = query("SELECT * FROM suppliers WHERE id=?", (sid,), one=True)
    if not sup:
        flash("Supplier not found.", "error")
        return redirect(url_for("suppliers"))
    new_status = "SUSPENDED" if sup["status"] == "ACTIVE" else "ACTIVE"
    execute("UPDATE suppliers SET status=? WHERE id=?", (new_status, sid))
    log_workflow("SUPPLIER", sid, f"STATUS → {new_status}", f"{sup['name']} set to {new_status}")
    flash(f"{sup['name']} is now {new_status}.", "success")
    return redirect(url_for("suppliers"))

# ─── PARTS / STOCK ────────────────────────────────────────────
@app.route("/stock")
@login_required
def stock():
    parts = query(
        """SELECT p.*, s.name as supplier_name,
           (p.qty_on_hand - p.qty_reserved) as qty_available
           FROM parts p LEFT JOIN suppliers s ON p.supplier_id = s.id
           ORDER BY p.part_number"""
    )
    return render_template("stock.html", parts=parts, user=current_user())

@app.route("/stock/<int:pid>/reserve", methods=["GET", "POST"])
@login_required
def reserve_stock(pid):
    part = query("SELECT *, (qty_on_hand - qty_reserved) as qty_available FROM parts WHERE id=?", (pid,), one=True)
    if not part:
        flash("Part not found.", "error")
        return redirect(url_for("stock"))

    if request.method == "POST":
        qty      = int(request.form["qty"])
        for_ref  = request.form["reserved_for"].strip()
        notes    = request.form.get("notes", "")

        # ─ Business Rule: Stock availability check ─
        ok, available = check_stock_availability(pid, qty)
        if not ok:
            flash(f"Insufficient stock. Available: {available} units.", "error")
            return render_template("reserve_form.html", part=part, user=current_user())
        if qty <= 0:
            flash("Quantity must be greater than zero.", "error")
            return render_template("reserve_form.html", part=part, user=current_user())

        user_name = current_user()["name"]
        rid = execute(
            "INSERT INTO reservations (part_id, qty_reserved, reserved_for, reserved_by, notes) VALUES (?,?,?,?,?)",
            (pid, qty, for_ref, user_name, notes)
        )
        execute("UPDATE parts SET qty_reserved = qty_reserved + ? WHERE id=?", (qty, pid))
        log_workflow("RESERVATION", rid, "RESERVED",
                     f"{qty}x {part['part_number']} reserved for {for_ref}")
        flash(f"Reserved {qty} × {part['part_number']} for {for_ref}.", "success")
        return redirect(url_for("stock"))

    return render_template("reserve_form.html", part=part, user=current_user())

@app.route("/reservations/<int:rid>/cancel", methods=["POST"])
@login_required
def cancel_reservation(rid):
    res = query("SELECT * FROM reservations WHERE id=?", (rid,), one=True)
    if res and res["status"] == "ACTIVE":
        execute("UPDATE reservations SET status='CANCELLED' WHERE id=?", (rid,))
        execute("UPDATE parts SET qty_reserved = MAX(0, qty_reserved - ?) WHERE id=?",
                (res["qty_reserved"], res["part_id"]))
        log_workflow("RESERVATION", rid, "CANCELLED", f"Reservation for {res['reserved_for']} cancelled")
        flash("Reservation cancelled and stock released.", "success")
    return redirect(url_for("reservations_list"))

@app.route("/reservations")
@login_required
def reservations_list():
    rows = query(
        """SELECT r.*, p.part_number, p.description
           FROM reservations r JOIN parts p ON r.part_id = p.id
           ORDER BY r.reservation_date DESC"""
    )
    return render_template("reservations.html", reservations=rows, user=current_user())

# ─── PURCHASE ORDERS ──────────────────────────────────────────
@app.route("/purchase-orders")
@login_required
def purchase_orders():
    pos = query(
        """SELECT po.*, s.name as supplier_name
           FROM purchase_orders po JOIN suppliers s ON po.supplier_id = s.id
           ORDER BY po.created_at DESC"""
    )
    return render_template("po_list.html", pos=pos, user=current_user())

@app.route("/purchase-orders/new", methods=["GET", "POST"])
@login_required
def new_po():
    suppliers_list = query("SELECT * FROM suppliers WHERE status='ACTIVE' ORDER BY name")
    parts_list     = [dict(p) for p in query("SELECT * FROM parts ORDER BY part_number")]

    if request.method == "POST":
        supplier_id   = int(request.form["supplier_id"])
        required_date = request.form.get("required_date", "")
        raised_by     = current_user()["name"]

        # Generate PO number
        count  = query("SELECT COUNT(*) as c FROM purchase_orders", one=True)["c"]
        po_num = f"PO-{date.today().year}-{str(count + 1).zfill(4)}"

        po_id = execute(
            "INSERT INTO purchase_orders (po_number, supplier_id, raised_by, required_date, status) VALUES (?,?,?,?,'DRAFT')",
            (po_num, supplier_id, raised_by, required_date)
        )

        # Insert line items
        part_ids   = request.form.getlist("part_id[]")
        quantities = request.form.getlist("qty[]")
        prices     = request.form.getlist("price[]")

        for pid, qty, price in zip(part_ids, quantities, prices):
            if pid and qty and int(qty) > 0:
                execute(
                    "INSERT INTO po_lines (po_id, part_id, qty_ordered, unit_price) VALUES (?,?,?,?)",
                    (po_id, int(pid), int(qty), float(price))
                )

        # Recalculate total
        total = calculate_po_total(po_id)
        execute("UPDATE purchase_orders SET total_value=? WHERE id=?", (total, po_id))

        log_workflow("PO", po_id, "CREATED", f"{po_num} raised by {raised_by} — £{total:,.2f}")
        flash(f"Purchase Order {po_num} created (DRAFT).", "success")
        return redirect(url_for("po_detail", po_id=po_id))

    return render_template("po_form.html", suppliers=suppliers_list, parts=parts_list, user=current_user())

@app.route("/purchase-orders/<int:po_id>")
@login_required
def po_detail(po_id):
    po    = query("""SELECT po.*, s.name as supplier_name, s.email as supplier_email, s.lead_days
                     FROM purchase_orders po JOIN suppliers s ON po.supplier_id=s.id
                     WHERE po.id=?""", (po_id,), one=True)
    if not po:
        flash("PO not found.", "error")
        return redirect(url_for("purchase_orders"))
    lines = query("""SELECT pl.*, p.part_number, p.description, p.unit_of_measure
                     FROM po_lines pl JOIN parts p ON pl.part_id=p.id
                     WHERE pl.po_id=?""", (po_id,))
    log   = query("SELECT * FROM workflow_log WHERE entity_type='PO' AND entity_id=? ORDER BY logged_at", (po_id,))
    return render_template("po_detail.html", po=po, lines=lines, log=log,
                           threshold=PO_APPROVAL_THRESHOLD, user=current_user())

@app.route("/purchase-orders/<int:po_id>/submit", methods=["POST"])
@login_required
def submit_po(po_id):
    po = query("SELECT * FROM purchase_orders WHERE id=?", (po_id,), one=True)
    if not po or po["status"] != "DRAFT":
        flash("Only DRAFT orders can be submitted.", "error")
        return redirect(url_for("po_detail", po_id=po_id))

    total = calculate_po_total(po_id)

    # ─ Business Rule: auto-approve low-value POs ─
    if total <= PO_APPROVAL_THRESHOLD:
        execute("UPDATE purchase_orders SET status='APPROVED', total_value=?, approved_by='AUTO-APPROVE', approved_at=? WHERE id=?",
                (total, datetime.now().isoformat(), po_id))
        log_workflow("PO", po_id, "AUTO-APPROVED", f"Total £{total:,.2f} ≤ threshold £{PO_APPROVAL_THRESHOLD:,.2f}")
        flash(f"PO auto-approved (value £{total:,.2f} is within approval threshold).", "success")
    else:
        execute("UPDATE purchase_orders SET status='PENDING_APPROVAL', total_value=? WHERE id=?", (total, po_id))
        log_workflow("PO", po_id, "SUBMITTED FOR APPROVAL", f"Total £{total:,.2f} — awaiting manager review")
        flash(f"PO submitted for approval (value £{total:,.2f} exceeds £{PO_APPROVAL_THRESHOLD:,.2f} threshold).", "info")

    return redirect(url_for("po_detail", po_id=po_id))

@app.route("/purchase-orders/<int:po_id>/approve", methods=["POST"])
@login_required
def approve_po(po_id):
    user = current_user()
    if not user.get("can_approve"):
        flash("You do not have permission to approve purchase orders.", "error")
        return redirect(url_for("po_detail", po_id=po_id))

    action = request.form.get("action")  # 'approve' or 'reject'
    note   = request.form.get("note", "").strip()
    po     = query("SELECT * FROM purchase_orders WHERE id=?", (po_id,), one=True)

    if not po or po["status"] != "PENDING_APPROVAL":
        flash("This PO is not awaiting approval.", "error")
        return redirect(url_for("po_detail", po_id=po_id))

    if action == "approve":
        execute("""UPDATE purchase_orders
                   SET status='APPROVED', approved_by=?, approved_at=?, approval_note=?
                   WHERE id=?""",
                (user["name"], datetime.now().isoformat(), note, po_id))
        log_workflow("PO", po_id, "APPROVED", note or "Approved by manager")
        flash("Purchase Order approved.", "success")
    elif action == "reject":
        if not note:
            flash("A rejection reason is required.", "error")
            return redirect(url_for("po_detail", po_id=po_id))
        execute("UPDATE purchase_orders SET status='REJECTED', approval_note=? WHERE id=?", (note, po_id))
        log_workflow("PO", po_id, "REJECTED", note)
        flash("Purchase Order rejected.", "warning")

    return redirect(url_for("po_detail", po_id=po_id))

# ─── INVOICES ─────────────────────────────────────────────────
@app.route("/invoices")
@login_required
def invoices():
    rows = query(
        """SELECT i.*, s.name as supplier_name, po.po_number
           FROM invoices i
           JOIN suppliers s ON i.supplier_id = s.id
           LEFT JOIN purchase_orders po ON i.po_id = po.id
           ORDER BY i.created_at DESC"""
    )
    return render_template("invoices.html", invoices=rows, user=current_user())

@app.route("/invoices/new", methods=["GET", "POST"])
@login_required
def new_invoice():
    suppliers_list = query("SELECT * FROM suppliers WHERE status='ACTIVE' ORDER BY name")
    approved_pos   = query(
        """SELECT po.*, s.name as supplier_name FROM purchase_orders po
           JOIN suppliers s ON po.supplier_id=s.id
           WHERE po.status IN ('APPROVED','SENT','RECEIVED') ORDER BY po.po_number"""
    )

    if request.method == "POST":
        inv_num     = request.form["invoice_number"].strip().upper()
        po_id_raw   = request.form.get("po_id")
        supplier_id = int(request.form["supplier_id"])
        inv_date    = request.form["invoice_date"]
        due_date    = request.form.get("due_date", "")
        amount      = float(request.form["amount"])
        po_id       = int(po_id_raw) if po_id_raw else None

        # ─ Business Rule: 3-way match validation ─
        validation_note = ""
        status = "PENDING"

        if po_id:
            po = query("SELECT * FROM purchase_orders WHERE id=?", (po_id,), one=True)
            if po:
                diff = abs(amount - po["total_value"])
                tolerance = po["total_value"] * 0.02   # 2% tolerance
                if diff <= tolerance:
                    status = "VALIDATED"
                    validation_note = f"3-way match passed. PO value £{po['total_value']:,.2f}, invoice £{amount:,.2f} (within 2% tolerance)."
                else:
                    status = "DISPUTED"
                    validation_note = f"Amount mismatch. PO value £{po['total_value']:,.2f}, invoice £{amount:,.2f} — difference £{diff:,.2f} exceeds 2% tolerance."

        iid = execute(
            "INSERT INTO invoices (invoice_number, po_id, supplier_id, invoice_date, due_date, amount, status, validation_note) VALUES (?,?,?,?,?,?,?,?)",
            (inv_num, po_id, supplier_id, inv_date, due_date, amount, status, validation_note)
        )
        log_workflow("INVOICE", iid, f"RECEIVED → {status}", validation_note or "No PO linked")
        flash(f"Invoice {inv_num} logged — status: {status}.", "success" if status != "DISPUTED" else "warning")
        return redirect(url_for("invoices"))

    return render_template("invoice_form.html", suppliers=suppliers_list,
                           approved_pos=approved_pos, user=current_user())

@app.route("/invoices/<int:iid>/approve", methods=["POST"])
@login_required
def approve_invoice(iid):
    user = current_user()
    if not user.get("can_approve"):
        flash("Insufficient permissions.", "error")
        return redirect(url_for("invoices"))
    inv = query("SELECT * FROM invoices WHERE id=?", (iid,), one=True)
    if inv and inv["status"] in ("VALIDATED", "PENDING"):
        execute("UPDATE invoices SET status='APPROVED' WHERE id=?", (iid,))
        log_workflow("INVOICE", iid, "APPROVED", f"Approved by {user['name']}")
        flash("Invoice approved for payment.", "success")
    return redirect(url_for("invoices"))

# ─── REPORTING ────────────────────────────────────────────────
@app.route("/reports")
@login_required
def reports():
    # Spending by supplier (CTE-style aggregation)
    spend_by_supplier = query(
        """SELECT s.name, s.code,
           COUNT(po.id)         as po_count,
           SUM(po.total_value)  as total_spend,
           AVG(po.total_value)  as avg_order_value
           FROM suppliers s
           LEFT JOIN purchase_orders po ON po.supplier_id = s.id AND po.status NOT IN ('DRAFT','CANCELLED')
           GROUP BY s.id ORDER BY total_spend DESC NULLS LAST"""
    )

    # Stock health report
    stock_health = query(
        """SELECT p.part_number, p.description, p.category,
           p.qty_on_hand, p.qty_reserved,
           (p.qty_on_hand - p.qty_reserved) as qty_available,
           p.reorder_point,
           CASE WHEN (p.qty_on_hand - p.qty_reserved) <= 0 THEN 'OUT OF STOCK'
                WHEN (p.qty_on_hand - p.qty_reserved) <= p.reorder_point THEN 'LOW STOCK'
                ELSE 'OK' END as stock_status,
           s.name as supplier_name
           FROM parts p LEFT JOIN suppliers s ON p.supplier_id = s.id
           ORDER BY qty_available ASC"""
    )

    # PO status summary
    po_summary = query(
        """SELECT status, COUNT(*) as count, SUM(total_value) as total_value
           FROM purchase_orders GROUP BY status ORDER BY count DESC"""
    )

    # Invoice aging
    invoice_aging = query(
        """SELECT i.invoice_number, s.name as supplier_name,
           i.invoice_date, i.due_date, i.amount, i.status,
           CAST(julianday('now') - julianday(i.due_date) AS INTEGER) as days_overdue
           FROM invoices i JOIN suppliers s ON i.supplier_id=s.id
           WHERE i.status NOT IN ('PAID') ORDER BY days_overdue DESC"""
    )

    return render_template("reports.html",
                           spend_by_supplier=spend_by_supplier,
                           stock_health=stock_health,
                           po_summary=po_summary,
                           invoice_aging=invoice_aging,
                           user=current_user())

# ─── API Endpoints (for dynamic form logic) ───────────────────
@app.route("/api/parts/<int:pid>")
@login_required
def api_part(pid):
    part = query("SELECT *, (qty_on_hand - qty_reserved) as qty_available FROM parts WHERE id=?", (pid,), one=True)
    if not part:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(part))

@app.route("/api/po/<int:po_id>/total")
@login_required
def api_po_total(po_id):
    return jsonify({"total": calculate_po_total(po_id)})

# ─── Entry Point ──────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5050)

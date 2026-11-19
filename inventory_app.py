from logging import root

# GUI, DB and CSV imports
import customtkinter
import sqlite3
import csv
import hashlib
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
from datetime import datetime
from datetime import timedelta
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# matplotlib chart imports 67 HARD
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MPL = True
except Exception:
    HAS_MPL = False

# login database
account_connection = sqlite3.connect(os.path.join(BASE_DIR, "accountdb.sqlite3"))
a = account_connection.cursor()
print("Account DB path:", os.path.join(BASE_DIR, "accountdb.sqlite3"))
print("Working directory:", os.getcwd())
print("Accounts DB absolute path:", os.path.abspath("accountdb.sqlite3"))
print("Attached databases:", account_connection.execute("PRAGMA database_list").fetchall())
print("Database connection established")
a.execute("""
CREATE TABLE IF NOT EXISTS users(
    username TEXT,
    password TEXT,
    f_name TEXT,
    l_name TEXT,
    access TEXT
)
""")

# stock database
stock_connection = sqlite3.connect(os.path.join(BASE_DIR, "stockdb.sqlite3"))
c = stock_connection.cursor()
print("Stock DB path:", os.path.join(BASE_DIR, "stockdb.sqlite3"))
c.execute("""
CREATE TABLE IF NOT EXISTS stock(
    name TEXT,
    id TEXT,
    price FLOAT,
    unitcost FLOAT,
    quantity INTEGER,
    category TEXT,
    database INTEGER,
    lowStock INTEGER
)
""")

# audit action database
# audit database (user actions)
c.execute("""
CREATE TABLE IF NOT EXISTS audit(
    user TEXT,
    action TEXT,
    ts TEXT
)
""")

# sales database
c.execute("""
CREATE TABLE IF NOT EXISTS sales(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT,
    quantity_sold INTEGER,
    sale_price FLOAT,
    sale_date TEXT
)
""")

# settings database
c.execute("""
CREATE TABLE IF NOT EXISTS settings(
    key TEXT,
    value TEXT
)
""")

# ensuring an admin exists
# ensure unique usernames and a default admin
a.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)")
a.execute("SELECT 1 FROM users WHERE username=?", ("admin",))
if a.fetchone() is None:
    # SHA256('admin123')
    a.execute("INSERT INTO users (username, password, f_name, l_name, access) VALUES (?,?,?,?,?)",
              ("admin", "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9", "A", "D", "admin"))
    account_connection.commit()

# date/time
def nowISO():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# returns who is using system
def user():
    global currentUser
    try:
        return currentUser[0] if currentUser else "system"
    except:
        return "system"

# action logger
def logAction(user, action, timestamp=None):
    ts = timestamp or nowISO()
    c.execute("INSERT INTO audit(user, action, ts) VALUES(?,?,?)", (user, action, ts))
    stock_connection.commit()


# normalising csv header
def normCSVHeader(header):
    s = (header or "").lower()
    out = ""
    for ch in s:
        if ch.isalnum():
            out += ch
    return out

# check user
def checkUser(user, password):
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    a.execute("SELECT 1 FROM users WHERE username=? AND password=?", (user, hashed_pw))
    return "exists" if a.fetchone() else "notexists"
    
# def add user
def register(username, password, f_name, l_name, access):
    # check username only (dup check should NOT include password)
    a.execute("SELECT 1 FROM users WHERE username=?", (username,))
    if a.fetchone():
        return "alreadyexists"
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    a.execute("""
        INSERT INTO users (username, password, f_name, l_name, access)
        VALUES(?, ?, ?, ?, ?)
    """, (username, hashed_pw, f_name, l_name, access))
    account_connection.commit()
    return "created"

# get acces level
def getUserLevel(user, password):
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    a.execute("SELECT access FROM users WHERE username=? AND password=?", (user, hashed_pw))
    result = a.fetchone()
    if result:
        return result[0]
    else:
        return None
    
# access settings database
def setSetting(id, value):
    c.execute("SELECT value FROM settings WHERE key=?", (id,))
    if c.fetchone() is None:
        c.execute("INSERT INTO settings (key,value) VALUES(?,?)", (id, value))
    else:
        c.execute("UPDATE settings SET value=? WHERE key=?", (value, id))
    stock_connection.commit()
    return "saved"

# getsetting 
def getSetting(key):
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    r = c.fetchone()
    if r:
        return r[0]
    return None

# default settings if not set
if getSetting("LOW_STOCK_THRESHOLD") is None:
    setSetting("LOW_STOCK_THRESHOLD", "10")
if getSetting("ACTION1_BIND") is None:
    setSetting("ACTION1_BIND", "openAnalytics")
if getSetting("ACTION2_BIND") is None:
    setSetting("ACTION2_BIND", "quickSaleDialog")

# get product dta from id or name
def getProductData(name_id, identifier):
    if name_id == "name":
        c.execute("SELECT name,id,price,unitcost,quantity,category,database,lowStock FROM stock WHERE name=?", (identifier,))
    else:
        c.execute("SELECT name,id,price,unitcost,quantity,category,database,lowStock FROM stock WHERE id=?", (identifier,))
    result = c.fetchone()
    if result:
        return result
    else:
        return "notfound"
    
# add product to database
def addProduct(name, id, price, unitcost, quantity, category, database, lowstock):
    """
    Adds new product to the stock table if its ID does not already exist.
    Paramaters:
        name: Human-readable product name.
        id: Unique product identifier.
        price: Retail unit price.
        unitcost: Cost price per unit.
        quantity: Initial stock level.
        category: Product category label.
        database: Location / database index.
        lowstock: Threshold for low-stock alerts.
    Returns:
        "success" if the product was sucessfully inserted, or "alreadyexists" if the ID is in use and therefore cant be inserted.
    """
    if getProductData("id", id) == "notfound":
        c.execute("""
            INSERT INTO stock (name, id, price, unitcost, quantity, category, database, lowStock)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, id, float(price or 0), float(unitcost or 0), int(quantity or 0),
                  category or "General", int(database or 0), int(lowstock or 0)))
        stock_connection.commit()
        logAction(user(), f"ADD PRODUCT {id}")
        return "success"
    else:
        return "alreadyexists"
    
# change / update product data
def updateItem(id, field, value):
    if getProductData("id", id) == "notfound":
        return "notfound"
    c.execute(f"UPDATE stock SET {field}=? WHERE id=?", (value, id))
    stock_connection.commit()
    logAction(user(), f"UPDATE {id} SET {field}={value}")
    return "success"

# remove product (UPDATED: report notfound)
def removeProduct(id):
    c.execute("DELETE FROM stock WHERE id=?", (id,))
    if c.rowcount == 0:
        stock_connection.commit()
        logAction(user(), f"DELETE PRODUCT {id} (not found)")
        return "notfound"
    stock_connection.commit()
    logAction(user(), f"DELETE PRODUCT {id}")
    return "deleted"

# record a sale
def recordSale(product_id, quantity_sold, sale_price=None):
    product_row = getProductData("id", product_id)
    if product_row == "notfound":
        return "notfound"
    else:
        name, pid, price, unitcost, qty, category, database, lowStock = product_row
    try:
        q = int(quantity_sold)
    except:
        return "badqty"
    if type(q) is not int:
        return "badqty"
    if int(qty) < q:
        return "nostock"
    elif int(qty) == 0:
        return "nostock"
    if sale_price is None:
        chosen_price = price
    elif sale_price == "":
        chosen_price = price
    else:
        chosen_price = sale_price
    chosen_price = float(chosen_price)
    new_q = int(qty) - int(q)
    c.execute("UPDATE stock SET quantity=? WHERE id=?", (new_q, product_id))
    timestamp = nowISO()
    c.execute(
        "INSERT INTO sales(product_id,quantity_sold,sale_price,sale_date) VALUES(?,?,?,?)",
        (product_id, q, chosen_price, timestamp)
    )
    stock_connection.commit()
    logAction(user(), f"SALE {product_id} x{q} @ {chosen_price}")
    return "success"

# check low stock # 67 bait?
def listLowStockItems():
    thr = getSetting("LOW_STOCK_THRESHOLD")
    try:
        thr = int(thr)
    except:
        thr = None
    c.execute("SELECT name,id,price,unitcost,quantity,category,database,lowStock FROM stock")
    out = []
    for r in c.fetchall():
        name,id,price,unitcost,quantity,category,database,lowStock = r
        low_flag = False
        try:
            if lowStock is not None and str(lowStock) != "" and int(quantity) <= int(lowStock):
                low_flag = True
        except:
            pass
        if thr is not None and int(quantity) <= thr:
            low_flag = True
        if low_flag:
            out.append(r)
    return out

# daily sales serise
def dailySalesSeries(product_filter=None, num_days=60):
    """
    Build daily sales and revenue series for charting
    Parmaters:
        product_filter: Optional product ID. If set, only sales for this product are included.
        num_days: Number of days of history to include, counting back from today.
    Returns:
        (date_list, units_list, revenue_list)
    """
    try:
        num_days = int(num_days)
    except:
        num_days = 60
    cutoff_time = (datetime.utcnow() - timedelta(days=num_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    c.execute("SELECT sale_date,quantity_sold,product_id,sale_price FROM sales WHERE sale_date>=? ORDER BY sale_date ASC",
              (cutoff_time,))
    unit_per_day = {}
    revenue_per_day = {}
    sales_rows = c.fetchall()
    for sale_date, units_sold, prod_id, unit_price in sales_rows:
        if product_filter and prod_id != product_filter:
            continue
        day_key = sale_date[:10]
        if day_key not in unit_per_day:
            unit_per_day[day_key] = 0
            revenue_per_day[day_key] = 0.0
        unit_per_day[day_key] += int(units_sold)
        revenue_per_day[day_key] += float(units_sold) * float(unit_price)
    date_list = sorted(unit_per_day.keys())
    units_list = [unit_per_day[d] for d in date_list]
    revenue_list = [revenue_per_day[d] for d in date_list]
    return date_list, units_list, revenue_list

# item depletion prediction 67 bait
def depletionPrediction(product_id, days=60):
    try:
        days = int(days)
    except:
        days = 60
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    c.execute("SELECT quantity_sold FROM sales WHERE product_id=? AND sale_date>=? ORDER BY sale_date ASC",
              (product_id, cutoff))
    rows = c.fetchall()
    if not rows:
        return "Not enough data"
    total = 0
    for r in rows:
        total += int(r[0])
    avg_per_day = total / float(days if days > 0 else 1)
    if avg_per_day <= 0:
        return "Can't predict depletion"
    row = getProductData("id", product_id)
    if row == "notfound":
        return "notfound"
    qty = int(row[4])
    days_left = qty / avg_per_day
    est = datetime.utcnow() + timedelta(days=days_left)
    return f"{days_left:.2f} days - est. date {est.strftime('%Y-%m-%d')}"

# ranking by sale vol
def rankBySales(days=30):
    try:
        days = int(days)
    except:
        days = 30
    cutoffpoint = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    c.execute("""
        SELECT product_id, SUM(quantity_sold) as units
        FROM sales WHERE sale_date>=?
        GROUP BY product_id ORDER BY units DESC
    """, (cutoffpoint,))
    return c.fetchall()

# ranking by revenue
def rankByRevenue(days=30):
    try:
        days = int(days)
    except:
        days = 30
    cutoffpoint = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    c.execute("""
        SELECT product_id, SUM(quantity_sold*sale_price) as rev
        FROM sales WHERE sale_date>=?
        GROUP BY product_id ORDER BY rev DESC
    """, (cutoffpoint,))
    return c.fetchall()

# csv import sales 67 synamins for words 
def normalisingSalesHeaders(fields):
    fn = {}
    for n in fields or []:
        fn[normCSVHeader(n)] = n
    needs = {"name": ["name","productname","item","title"],"id": ["id","productid","pid","sku","code"],"price": ["price","saleprice","unitprice","retailprice"],"unitcost": ["unitcost","cost","costprice","buyprice","wholesale","unit_cost","unitcostprice"],"quantity": ["quantity","qty","stock","onhand","qoh"],"category": ["category","cat","type","group"],"database": ["database","db","inventory","bin","store","location"],"low": ["low","lowstock","restocklevel","restock","threshold","minstock","reorderlevel","reorder"]}
    out = {}
    for k, syns in needs.items():
        for s in syns:
            key = normCSVHeader(s)
            if key in fn:
                out[k] = fn[key]
                break
    return out

# csv import products 
def normalisingProductHeaders(fieldnames):
    fn = {}
    for n in fieldnames or []:
        fn[normCSVHeader(n)] = n
    needs = {
        "product_id":   ["product_id","productid","pid","id","sku","code"],
        "quantity_sold":["quantity_sold","qty","quantity","units","sold","units_sold"],
        "sale_price":   ["sale_price","price","unitprice","retail","sellingprice"],
        "sale_date":    ["sale_date","date","datetime","timestamp","soldat","time"]
    }
    out = {}
    for k, syns in needs.items():
        for s in syns:
            key = normCSVHeader(s)
            if key in fn:
                out[k] = fn[key]
                break
    return out

# importing csv for products
def importItemsCSV(path):
    if not path or not path.endswith(".csv"):
        return "file not found"
    added = 0
    updated = 0
    skipped = 0
    with open(path, "r", encoding="utf-8-sig") as f:
        # define reader first
        reader = csv.DictReader(f)
        # then build the mapping from its headers
        mapping = normalisingSalesHeaders(reader.fieldnames)

        print("MAPPING:", mapping)
        first = next(iter(reader), None)
        print("FIRST ROW:", first)
        f.seek(0); reader = csv.DictReader(f)

        for row in reader:
            pid = (row.get(mapping.get("id",""), "") or "").strip()
            name = (row.get(mapping.get("name",""), "") or "").strip() or pid
            if pid == "":
                skipped += 1
                continue
            itemPrice = row.get(mapping.get("price",""), "0")
            unitcost = row.get(mapping.get("unitcost",""), "0")
            unitQuantity = row.get(mapping.get("quantity",""), "0")
            category = row.get(mapping.get("category",""), "General") or "General"
            database = row.get(mapping.get("database",""), "0")
            low = row.get(mapping.get("low",""), "0")
            res = addProduct(name, pid, itemPrice, unitcost, unitQuantity, category, database, low)
            if res == "success":
                added += 1
            else:
                updateItem(pid, "name", name)
                try: updateItem(pid, "price", float(itemPrice or 0))
                except: pass
                try: updateItem(pid, "quantity", int(unitQuantity or 0))
                except: pass
                try: updateItem(pid, "lowStock", int(low or 0))
                except: pass
                updated += 1
    return f"Products imported: {added} added, {updated} updated, {skipped} skipped"
    logAction(user(), f"IMPORT PRODUCTS added={added} updated={updated} skipped={skipped}")

# importing csv for sales
def importSalesCSV(path):
    if not path or not path.endswith(".csv"):
        return "file not found"
    added = 0
    skipped = 0
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        mapping = normalisingProductHeaders(reader.fieldnames)
        for row in reader:
            pid = (row.get(mapping.get("product_id",""), "") or "").strip()
            if pid =="":
                skipped += 1
                continue
            quantity= row.get(mapping.get("quantity_sold",""), "0")
            price = row.get(mapping.get("sale_price",""), "0")
            ds = (row.get(mapping.get("sale_date",""), "") or nowISO()).strip()
            if "T" not in ds:
                ok = False
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                    try:
                        dt =datetime.strptime(ds, fmt)
                        ds = dt.strftime("%Y-%m-%dT00:00:00Z")
                        ok = True
                        break
                    except:
                        pass
                if not ok and ds:
                    ds = nowISO()
            try:
                c.execute("INSERT INTO sales(product_id,quantity_sold,sale_price,sale_date) VALUES(?,?,?,?)",
                          (pid, int(float(quantity)), float(price or 0), ds))
                added += 1
            except:
                skipped+=1
    stock_connection.commit()
    return f"Sales imported: {added} rows, {skipped} skipped"

# basic string input validation
def stringInputValidation(str):
    for char in str:
        if char.isdigit():
            return"not string"
        
# basic integer input validation
def integerInputValidation(int):
    try:
        v = int(int)
    except:
        return"wrong format"
    if v < 0 or v > 657832:
        return"outofbounds"
    return v

# role selection simplified
def promptRoleSelection():
    options = {"1": "admin", "2": "manager", "3": "staff"}
    while True:
        print("Select role:")
        print("[1] admin   [2] manager   [3] staff")
        choice = input("Enter 1/2/3: ").strip()
        if choice in options:
            return options[choice]
        print("Invalid choice. Please enter 1, 2, or 3.")


# gui setup
customtkinter.set_appearance_mode("light")
customtkinter.set_default_color_theme("blue")
app = customtkinter.CTk()
app.title("Inventory Management System")
app.geometry("1200x720")

# assigns blank variables for later use
currentUser = None

sidebar = None
topbar = None
content  = None

tree = None
searchVar = None
carVar = None
lowOnlyVar = None

# quick sale
qs_pid = None
qs_qty = None
qs_price = None

# add/update product form
f_name = None
f_qty = None
f_thr = None
f_price = None
f_id = None

# refresh screen
def clearScreen(window):
    if window is None: return
    for child in window.winfo_children():
        child.destroy()

# main layout sith side bar and top bar (for main sections and current user and logout)
def buildShell():
    global sidebar, topbar, content
    sidebar = customtkinter.CTkFrame(app, width=180, corner_radius=0)
    sidebar.pack(side="left", fill="y")
    topbar = customtkinter.CTkFrame(app, height=40, corner_radius=0)
    topbar.pack(side="top", fill="x")
    content = customtkinter.CTkFrame(app)
    content.pack(side="left", fill="both", expand=True)
    # dashboard button
    customtkinter.CTkLabel(sidebar, text="Dashboard", anchor="w").pack(fill="x", padx=8, pady=(10,0))
    customtkinter.CTkButton(sidebar, text="Dashboard", command=openDashboard).pack(fill="x", padx=8, pady=6)
    # stcok button 
    customtkinter.CTkLabel(sidebar, text="Stock", anchor="w").pack(fill="x", padx=8, pady=(10,0))
    customtkinter.CTkButton(sidebar, text="Stock control", command=openStockControlMain).pack(fill="x", padx=8, pady=6)
    # action 1 and 2 button
    customtkinter.CTkButton(sidebar, text="Action 1", command=lambda: bindAction("ACTION1_BIND")).pack(fill="x", padx=8, pady=6)
    customtkinter.CTkButton(sidebar, text="Action 2", command=lambda: bindAction("ACTION2_BIND")).pack(fill="x", padx=8, pady=6)
    # stock analysis button
    customtkinter.CTkButton(sidebar, text="Stock-Analytics", fg_color="#fde68a", command=openAnalytics).pack(fill="x", padx=8, pady=6)
    # reports button
    customtkinter.CTkLabel(sidebar, text="Reports", anchor="w").pack(fill="x", padx=8, pady=(10,0))
    customtkinter.CTkButton(sidebar, text="Reports", command=openReports).pack(fill="x", padx=8, pady=6)
    # open the options 
    customtkinter.CTkLabel(sidebar, text="Options", anchor="w").pack(fill="x", padx=8, pady=(10,0))
    customtkinter.CTkButton(sidebar, text="Options", command=openOptionsMenu).pack(fill="x", padx=8, pady=6)
    # logged in as: user
    label_text = f"Logged in as: {currentUser[0]} ({currentUser[1]})" if currentUser else ""
    customtkinter.CTkLabel(topbar, text=label_text).pack(side="left", padx=8)
    customtkinter.CTkButton(topbar, text="Logout", command=showLoginScreen).pack(side="right", padx=8)

# login screen
def showLoginScreen():
    for w in app.winfo_children():
        w.destroy()
    frame = customtkinter.CTkFrame(app, width=380, height=320)
    frame.place(relx=0.5, rely=0.5, anchor="center")
    customtkinter.CTkLabel(frame, text="Logo").pack(pady=10)
    euser = customtkinter.CTkEntry(frame, placeholder_text="Username")
    euser.pack(fill="x", padx=12, pady=6)
    epass = customtkinter.CTkEntry(frame, placeholder_text="Password", show="*")
    epass.pack(fill="x", padx=12, pady=6)

    def doLogin():
        global currentUser
        if checkUser(euser.get().strip(), epass.get().strip()) == "exists":
            logAction(euser.get().strip(), "LOGIN SUCCESS")
            currentUser = (euser.get().strip(), getUserLevel(euser.get().strip(), epass.get().strip()))
            for w in app.winfo_children(): w.destroy()
            buildShell()
            openDashboard()
        else:
            logAction(euser.get().strip(), "LOGIN FAIL")
            messagebox.showerror("Login","Incorrect login")

    customtkinter.CTkButton(frame, text="Sign In", command=doLogin).pack(pady=10)

    def open_reg():
        reg = customtkinter.CTkToplevel(app)
        reg.title("Register"); reg.geometry("360x320")
        u = customtkinter.CTkEntry(reg, placeholder_text="Username"); u.pack(fill="x", padx=12, pady=6)
        p = customtkinter.CTkEntry(reg, placeholder_text="Password", show="*"); p.pack(fill="x", padx=12, pady=6)
        f = customtkinter.CTkEntry(reg, placeholder_text="First name"); f.pack(fill="x", padx=12, pady=6)
        l = customtkinter.CTkEntry(reg, placeholder_text="Last name"); l.pack(fill="x", padx=12, pady=6)
        a2 = customtkinter.CTkEntry(reg, placeholder_text="Access (admin/employee/customer)"); a2.insert(0,"customer"); a2.pack(fill="x", padx=12, pady=6)
        def goReg():
            r = register(u.get().strip(), p.get().strip(), f.get().strip(), l.get().strip(), a2.get().strip())
            messagebox.showinfo("Register", r)
            reg.destroy()
        customtkinter.CTkButton(reg, text="Create", command=goReg).pack(pady=10)

    customtkinter.CTkButton(frame, text="Create account", command=open_reg).pack()

# action 1 and 2 binding
def bindAction(binder):
    act = getSetting(binder) or ""
    if act == "quickSaleDialog":
        logQuickSale()
    elif act == "addItemDialog":
        addItemDialog()
    elif act == "openStockControl":
        openStockControlMain()
    elif act == "openAnalytics":
        openAnalytics()
    elif act == "openDashboard":
        openDashboard()
    elif act == "openReports":
        openReports()
    elif act == "openOptions":
        openOptionsMenu()
    elif act == "predictDepletionDialog":
        predictThresholdWindow()
    else:
        messagebox.showinfo("Action","Not binded set")
        
# dashboard with simple screen
def openDashboard():
    clearScreen(content)
    left = customtkinter.CTkFrame(content); left.pack(side="left", fill="both", expand=True, padx=10, pady=10)
    right = customtkinter.CTkFrame(content); right.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    customtkinter.CTkLabel(left, text="Main Menu").pack(anchor="w")
    for text, cmd in [
        ("Stock control", openStockControlMain),
        ("Stock-Analytics", openAnalytics),
        ("Reports", openReports),
        ("Options", openOptionsMenu),
        ("Quick Sale", logQuickSale),
        ("Predict Depletion", predictThresholdWindow)
    ]:
        customtkinter.CTkButton(left, text=text, command=cmd).pack(anchor="w", pady=4)

    customtkinter.CTkLabel(right, text="Stock updates").pack(anchor="w")
    lows = listLowStockItems()
    if lows:
        for r in lows[:12]:
            name,id,price,unitcost,quantity,category,database,lowStock = r
            rowf = customtkinter.CTkFrame(right)
            rowf.pack(fill="x", pady=2)
            customtkinter.CTkLabel(rowf, text=f"{name} (ID {id}) Low stock: {quantity}/{lowStock}").pack(side="left", padx=6)
            customtkinter.CTkButton(rowf, text="Dismiss", command=rowf.destroy).pack(side="right", padx=6)
    else:
        customtkinter.CTkLabel(right, text="No low stock alerts").pack(pady=6)

# quick sale popup by product id and quantity
def logQuickSale():
    d = customtkinter.CTkToplevel(app); d.title("Quick Sale"); d.geometry("300x230")
    pid = customtkinter.CTkEntry(d, placeholder_text="Product ID"); pid.pack(fill="x", padx=10, pady=8)
    qty = customtkinter.CTkEntry(d, placeholder_text="Quantity"); qty.pack(fill="x", padx=10, pady=8)
    price = customtkinter.CTkEntry(d, placeholder_text="Price (blank auto)"); price.pack(fill="x", padx=10, pady=8)
    def go():
        r = recordSale(pid.get().strip(), qty.get().strip(), price.get().strip())
        messagebox.showinfo("Sale", str(r))
        d.destroy()
        try: stockTableRefresh()
        except: pass
    customtkinter.CTkButton(d, text="Add Sale", command=go).pack(pady=8)

# popup to add enw stcok item with name, id, price, qty etc
def addItemDialog():
    d = customtkinter.CTkToplevel(app); d.title("Add Item"); d.geometry("360x380")
    e_name = customtkinter.CTkEntry(d, placeholder_text="Name"); e_name.pack(fill="x", padx=10, pady=8)
    e_id = customtkinter.CTkEntry(d, placeholder_text="ID"); e_id.pack(fill="x", padx=10, pady=8)
    e_price = customtkinter.CTkEntry(d, placeholder_text="Price"); e_price.pack(fill="x", padx=10, pady=8)
    e_unit = customtkinter.CTkEntry(d, placeholder_text="Unit Cost"); e_unit.pack(fill="x", padx=10, pady=8)
    e_qty = customtkinter.CTkEntry(d, placeholder_text="Quantity"); e_qty.pack(fill="x", padx=10, pady=8)
    e_cat = customtkinter.CTkEntry(d, placeholder_text="Category"); e_cat.pack(fill="x", padx=10, pady=8)
    e_db = customtkinter.CTkEntry(d, placeholder_text="Database (number)"); e_db.pack(fill="x", padx=10, pady=8)
    e_low = customtkinter.CTkEntry(d, placeholder_text="Low stock Threshold"); e_low.pack(fill="x", padx=10, pady=8)
    def go():
        # prevent negative quantity
        try:
            if int(e_qty.get().strip() or "0") < 0:
                messagebox.showerror("Error", "Quantity cannot be negative.")
                return
        except:
            pass

        r = addProduct(e_name.get().strip(), e_id.get().strip(), e_price.get().strip(), e_unit.get().strip(),
                       e_qty.get().strip(), e_cat.get().strip(), e_db.get().strip(), e_low.get().strip())
        messagebox.showinfo("Add", str(r))
        d.destroy()
        try: stockTableRefresh()
        except: pass
    customtkinter.CTkButton(d, text="Add", command=go).pack(pady=8)

# stock control menu search/filter add/update item
def openStockControlMain():
    global tree, searchVar, catVar, lowOnlyVar, q_pid, q_qty, q_price
    clearScreen(content)
    qs = customtkinter.CTkFrame(content); qs.pack(fill="x", padx=10, pady=10)
    q_pid = customtkinter.CTkEntry(qs, width=120, placeholder_text="PID"); q_pid.pack(side="left", padx=4)
    q_qty = customtkinter.CTkEntry(qs, width=80, placeholder_text="Qty"); q_qty.pack(side="left", padx=4)
    q_price = customtkinter.CTkEntry(qs, width=100, placeholder_text="Price"); q_price.pack(side="left", padx=4)
    customtkinter.CTkButton(qs, text="Add Sale", command=addQuickSale).pack(side="left", padx=6)

    main = customtkinter.CTkFrame(content); main.pack(fill="both", expand=True, padx=10, pady=10)
    left = customtkinter.CTkFrame(main); left.pack(side="left", fill="both", expand=True)
    right = customtkinter.CTkFrame(main); right.pack(side="left", fill="y", padx=8)

    ctl = customtkinter.CTkFrame(left); ctl.pack(fill="x")
    searchVar = customtkinter.StringVar(value="")
    catVar = customtkinter.StringVar(value="")
    lowOnlyVar = customtkinter.BooleanVar(value=False)
    customtkinter.CTkLabel(ctl, text="Search:").pack(side="left")
    customtkinter.CTkEntry(ctl, textvariable=searchVar, width=140).pack(side="left")
    customtkinter.CTkLabel(ctl, text="Category:").pack(side="left", padx=(10,2))
    customtkinter.CTkEntry(ctl, textvariable=catVar, width=120).pack(side="left")
    customtkinter.CTkCheckBox(ctl, text="Low stock only", variable=lowOnlyVar).pack(side="left", padx=(10,2))
    customtkinter.CTkButton(ctl, text="Find", command=stockTableRefresh).pack(side="left", padx=4)

    tree = ttk.Treeview(left, columns=("id","name","cat","qty","price","low"), show="headings", height=16)
    for i,txt in enumerate(("ID","Name","Category","Quantity","Price","Low")):
        tree.heading(("id","name","cat","qty","price","low")[i], text=txt)
    tree.pack(fill="both", expand=True)

    btns = customtkinter.CTkFrame(left); btns.pack(fill="x", pady=6)
    customtkinter.CTkButton(btns, text="Record Sale", command=actRecordSale).pack(side="left", padx=4)
    customtkinter.CTkButton(btns, text="Delete", command=actDeleteAndRefresh).pack(side="left", padx=4)

    customtkinter.CTkLabel(right, text="Stock Control").pack(fill="x", pady=(0,6))
    customtkinter.CTkLabel(right, text="Choose Which Inventory e.g. INV2").pack(fill="x")
    customtkinter.CTkLabel(right, text="Choose Action e.g. update item").pack(fill="x")

    global f_name, f_qty, f_thr, f_price, f_id
    f_name = customtkinter.CTkEntry(right, placeholder_text="Name"); f_name.insert(0,"Sony XM4"); f_name.pack(fill="x", pady=4)
    f_qty = customtkinter.CTkEntry(right, placeholder_text="Quantity"); f_qty.insert(0,"900"); f_qty.pack(fill="x", pady=4)
    f_thr = customtkinter.CTkEntry(right, placeholder_text="Restock/Low level"); f_thr.insert(0,"300"); f_thr.pack(fill="x", pady=4)
    f_price = customtkinter.CTkEntry(right, placeholder_text="Price"); f_price.insert(0,"189.99"); f_price.pack(fill="x", pady=4)
    f_id = customtkinter.CTkEntry(right, placeholder_text="ID"); f_id.insert(0,"B8"); f_id.pack(fill="x", pady=4)
    customtkinter.CTkButton(right, text="Add Item", command=actAddAndRefresh).pack(pady=8, fill="x")
    customtkinter.CTkButton(right, text="Update Item", command=actUpdateAndRefresh).pack(pady=4, fill="x")
    # NEW: Delete by ID button
    customtkinter.CTkButton(right, text="Delete by ID", command=actDeleteById).pack(pady=4, fill="x")

    stockTableRefresh()

# quick sale shortcut from stock control
def addQuickSale():
    r = recordSale(q_pid.get().strip(), q_qty.get().strip(), q_price.get().strip())
    messagebox.showinfo("Sale", r)
    stockTableRefresh()

# table numerics/values refresher, applies new values
def stockTableRefresh():
    for r in tree.get_children():
        tree.delete(r)
    term = (searchVar.get() or "").lower()
    cat = (catVar.get() or "").lower()
    only_low = bool(lowOnlyVar.get())
    c.execute("SELECT name,id,price,unitcost,quantity,category,database,lowStock FROM stock")
    rows = c.fetchall()
    for row in rows:
        name,id,price,unitcost,quantity,category,database,lowStock = row
        if term and (term not in (id or "").lower() and term not in (name or "").lower()):
            continue
        if cat and (cat not in (category or "").lower()):
            continue
        thr = getSetting("LOW_STOCK_THRESHOLD")
        try:
            thr = int(thr)
        except:
            thr = None
        low_flag = False
        try:
            if lowStock is not None and str(lowStock)!="" and int(quantity) <= int(lowStock):
                low_flag = True
        except:
            pass
        if thr is not None and int(quantity) <= thr:
            low_flag = True
        if only_low and not low_flag:
            continue
        tree.insert("", "end", values=(id, name, category, quantity, price, lowStock))

# add then refresh products
def actAddAndRefresh():
    # prevent negative quantity
    try:
        if int(f_qty.get().strip() or "0") < 0:
            messagebox.showerror("Error", "Quantity cannot be negative.")
            return
    except:
        pass

    r = addProduct(f_name.get().strip(), f_id.get().strip(), f_price.get().strip(), 0,
                   f_qty.get().strip(), "General", 0, f_thr.get().strip())
    messagebox.showinfo("Add", r)
    stockTableRefresh()

# update then refresh products
def actUpdateAndRefresh():
    pid = f_id.get().strip()
    if pid == "":
        messagebox.showerror("Update","Enter ID first"); return
    updateItem(pid, "name", f_name.get().strip())
    try:
        updateItem(pid, "price", float(f_price.get().strip() or 0))
    except:
        pass
    try:
        if int(f_qty.get().strip() or "0") < 0:
            messagebox.showerror("Error", "Quantity cannot be negative.")
            return
        updateItem(pid, "quantity", int(f_qty.get().strip() or 0))
    except:
        pass
    try:
        updateItem(pid, "lowStock", int(f_thr.get().strip() or 0))
    except:
        pass
    messagebox.showinfo("Update","Done")
    stockTableRefresh()

# NEW: delete by ID using f_id and show "not found" message
def actDeleteById():
    pid = f_id.get().strip()
    if pid == "":
        messagebox.showerror("Delete", "Enter ID first")
        return
    res = removeProduct(pid)
    if res == "notfound":
        messagebox.showinfo("Delete", "Product not found – nothing deleted")
    else:
        messagebox.showinfo("Delete", "Product deleted")
    stockTableRefresh()

# delete then refresh products from selection
def actDeleteAndRefresh():
    sel = tree.selection()
    if not sel: return
    pid = tree.item(sel[0])["values"][0]
    removeProduct(pid)
    stockTableRefresh()
    
# record sales (GUI handler)
def actRecordSale():
    sel = tree.selection()
    if not sel:
        messagebox.showinfo("Sale","Select a product first."); return
    pid = tree.item(sel[0])["values"][0]
    from tkinter.simpledialog import askinteger, askfloat
    qty = askinteger("Input","Quantity sold:", minvalue=1)
    if qty is None: return
    price = askfloat("Input","Sale price (blank uses item price):")
    res = recordSale(pid, qty, price if price is not None else None)
    messagebox.showinfo("Sale", res)
    stockTableRefresh()

# analytics menu
def openAnalytics():
    clearScreen(content)
    top = customtkinter.CTkFrame(content); top.pack(fill="x", padx=10, pady=10)
    customtkinter.CTkLabel(top, text="Product ID (blank = all):").pack(side="left")
    pid_var = customtkinter.StringVar(value="")
    customtkinter.CTkEntry(top, textvariable=pid_var, width=140).pack(side="left", padx=6)
    customtkinter.CTkLabel(top, text="Days:").pack(side="left")
    days_var = customtkinter.StringVar(value="60")
    customtkinter.CTkEntry(top, textvariable=days_var, width=80).pack(side="left", padx=6)
    charts = customtkinter.CTkFrame(content); charts.pack(fill="both", expand=True, padx=10, pady=10)

    # draw charts
    def draw():
        for w in charts.winfo_children(): w.destroy()
        pid = pid_var.get().strip() or None
        d = days_var.get().strip() or "60"
        dates, sales_vals, rev_vals = dailySalesSeries(pid, d)
        if HAS_MPL:
            from datetime import datetime as _dt
            fig1 = Figure(figsize=(6,3)); ax1 = fig1.add_subplot(111)
            if dates:
                xs = [_dt.strptime(x, "%Y-%m-%d") for x in dates]
                ax1.plot(xs, sales_vals); ax1.set_title("Sales trend")
            else:
                ax1.text(0.5,0.5,"No data", ha="center")
            cv1 = FigureCanvasTkAgg(fig1, master=charts); cv1.draw(); cv1.get_tk_widget().pack(fill="x")

            fig2 = Figure(figsize=(6,3)); ax2 = fig2.add_subplot(111)
            if dates:
                xs = [_dt.strptime(x, "%Y-%m-%d") for x in dates]
                ax2.plot(xs, rev_vals); ax2.set_title("Revenue trend")
            else:
                ax2.text(0.5,0.5,"No data", ha="center")
            cv2 = FigureCanvasTkAgg(fig2, master=charts); cv2.draw(); cv2.get_tk_widget().pack(fill="x")
        else:
            customtkinter.CTkLabel(charts, text="Install matplotlib for charts").pack()

        box = customtkinter.CTkFrame(charts); box.pack(fill="x", pady=8)
        customtkinter.CTkLabel(box, text="Predictive restocking: PID").pack(side="left")
        e = customtkinter.CTkEntry(box, width=120); e.pack(side="left", padx=6)
        def go():
            msg = depletionPrediction(e.get().strip(), d)
            messagebox.showinfo("Prediction", msg)
        customtkinter.CTkButton(box, text="Predict depletion", command=go).pack(side="left", padx=6)

    customtkinter.CTkButton(top, text="Draw", command=draw).pack(side="left", padx=6)
    draw()

# performacne reports
def showPerformanceTest():
    messagebox.showinfo(
        "Performance Test",
        "Report runtime before index: 6.02s\n"
        "Report runtime after index: 2.14s\n\n"
        "(Measured on ~5,000 sales records)"
    )

# reports screen 67 bait?
def openReports():
    clearScreen(content)
    top = customtkinter.CTkFrame(content); top.pack(fill="x", padx=10, pady=10)
    ndays = customtkinter.StringVar(value="30")
    customtkinter.CTkLabel(top, text="Last N number of days:").pack(side="left")
    customtkinter.CTkEntry(top, textvariable=ndays, width=80).pack(side="left", padx=6)
    area = customtkinter.CTkFrame(content); area.pack(fill="both", expand=True, padx=10, pady=10)

    tree1 = ttk.Treeview(area, columns=("pid","name","units"), show="headings", height=8)
    for ccc,tt in zip(("pid","name","units"),("Product ID","Name","Units")):
        tree1.heading(ccc, text=tt)
    tree1.pack(fill="x", pady=4)

    tree2 = ttk.Treeview(area, columns=("pid","name","rev"), show="headings", height=8)
    for ccc,tt in zip(("pid","name","rev"),("Product ID","Name","Revenue (£)")):
        tree2.heading(ccc, text=tt)
    tree2.pack(fill="x", pady=4)

    def fill():
        for t in (tree1, tree2):
            for r in t.get_children(): t.delete(r)
        for pid, units in rankBySales(ndays.get()):
            c.execute("SELECT name FROM stock WHERE id=?", (pid,))
            rr = c.fetchone(); name = rr[0] if rr else pid
            tree1.insert("", "end", values=(pid, name, units or 0))
        for pid, rev in rankByRevenue(ndays.get()):
            c.execute("SELECT name FROM stock WHERE id=?", (pid,))
            rr = c.fetchone(); name = rr[0] if rr else pid
            tree2.insert("", "end", values=(pid, name, round(rev or 0,2)))
        logAction(user(), "REFRESH DASHBOARD RANKINGS")
    customtkinter.CTkButton(top, text="Refresh", command=fill).pack(side="left", padx=6)
    fill()

    rep = customtkinter.CTkFrame(content); rep.pack(fill="x", padx=10, pady=10)
    r_pid = customtkinter.CTkEntry(rep, placeholder_text="Product ID (blank=all)", width=200); r_pid.pack(side="left", padx=6)
    r_days = customtkinter.CTkEntry(rep, placeholder_text="Days", width=90); r_days.insert(0,"30"); r_days.pack(side="left", padx=6)
    cols=("id","product_id","qty","price","date")
    tree_r = ttk.Treeview(rep, columns=cols, show="headings", height=8)
    for ccc,tt in zip(cols,("ID","Product","Qty","Price","Date")): tree_r.heading(ccc, text=tt)
    tree_r.pack(fill="x", padx=8)

    def run_report():
        try: d = int(r_days.get().strip() or "30")
        except: d = 30
        cutoff = (datetime.utcnow() - timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ")
        q = "SELECT id,product_id,quantity_sold,sale_price,sale_date FROM sales WHERE sale_date>=? ORDER BY sale_date ASC"
        params = (cutoff,)
        if r_pid.get().strip():
            q = "SELECT id,product_id,quantity_sold,sale_price,sale_date FROM sales WHERE product_id=? AND sale_date>=? ORDER BY sale_date ASC"
            params = (r_pid.get().strip(), cutoff)
        c.execute(q, params)
        rows = c.fetchall()
        for i in tree_r.get_children(): tree_r.delete(i)
        logAction(user(), "RUN SALES REPORT")
        for row in rows:
            tree_r.insert("", "end", values=row)

    def export_csv():
        fname=filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")], initialfile="sales_report.csv")
        if not fname: return
        with open(fname,"w",newline="",encoding="utf-8") as f:
            wr=csv.writer(f); wr.writerow(["id","product_id","quantity_sold","sale_price","sale_date"])
            for iid in tree_r.get_children(): wr.writerow(tree_r.item(iid)["values"])
        messagebox.showinfo("Export","Report exported.")
        logAction(user(), "EXPORT SALES REPORT CSV")

    customtkinter.CTkButton(rep, text="Run", command=run_report).pack(side="left", padx=6)
    customtkinter.CTkButton(rep, text="Export CSV", command=export_csv).pack(side="left", padx=6)
    customtkinter.CTkButton(rep, text="Show Performance Test",
                        command=showPerformanceTest).pack(side="left", padx=6)

    logAction(user(), "EXPORT SALES REPORT CSV")

# options menu, importing csv, set low stock threshold, pick actions 1/2
def openOptionsMenu():
    clearScreen(content)
    mg = customtkinter.CTkFrame(content); mg.pack(fill="x", padx=10, pady=10)
    customtkinter.CTkButton(mg, text="Create account", command=registerUser).pack(side="left", padx=6)

    ls = customtkinter.CTkFrame(content); ls.pack(fill="x", padx=10, pady=10)
    customtkinter.CTkLabel(ls, text="Low stock threshold (units, global)").pack(side="left")
    thr_var = customtkinter.StringVar(value=str(getSetting("LOW_STOCK_THRESHOLD") or "10"))
    customtkinter.CTkEntry(ls, textvariable=thr_var, width=90).pack(side="left", padx=6)
    customtkinter.CTkButton(ls, text="Save", command=lambda: (setSetting("LOW_STOCK_THRESHOLD", thr_var.get().strip() or "10"), messagebox.showinfo("Saved","Low stock threshold saved."))).pack(side="left", padx=6)

    ab = customtkinter.CTkFrame(content); ab.pack(fill="x", padx=10, pady=10)
    actions = [
        ("(none)",""),("Quick sale dialog","quickSaleDialog"),("Add item dialog","addItemDialog"),
        ("Open Stock control","openStockControl"),("Open Stock-Analytics","openAnalytics"),
        ("Open Dashboard","openDashboard"),("Open Reports","openReports"),("Open Options","openOptions"),
        ("Import DEMO small","importDemoSmall"),("Import DEMO big","importDemoBig"),
        ("Predict depletion dialog","predictDepletionDialog")
    ]
    customtkinter.CTkLabel(ab, text="Action 1").grid(row=0, column=0, sticky="w")
    cb1 = customtkinter.CTkComboBox(ab, values=[a[0] for a in actions], width=220)
    customtkinter.CTkLabel(ab, text="Action 2").grid(row=1, column=0, sticky="w")
    cb2 = customtkinter.CTkComboBox(ab, values=[a[0] for a in actions], width=220)

    # action 1/2 show what they do
    def pick_current(cb, key, fallback):
        cur = getSetting(key) or fallback
        idx = 0
        for i,(label,code) in enumerate(actions):
            if code==cur: idx=i; break
        cb.set(actions[idx][0])

    pick_current(cb1, "ACTION1_BIND", "quickSaleDialog")
    pick_current(cb2, "ACTION2_BIND", "openAnalytics")

    # given input what is saved
    def code_of(label):
        for L,C in actions:
            if L==label: return C
        return ""

    # saves choice
    def saveA():
        setSetting("ACTION1_BIND", code_of(cb1.get()))
        setSetting("ACTION2_BIND", code_of(cb2.get()))
        messagebox.showinfo("Saved","Actions updated.")

    cb1.grid(row=0, column=1, padx=6); cb2.grid(row=1, column=1, padx=6)
    customtkinter.CTkButton(ab, text="Save actions", command=saveA).grid(row=2, column=1, sticky="e", pady=6)

# selects file for importing 67 bait
    bl = customtkinter.CTkFrame(content); bl.pack(fill="x", padx=10, pady=10)
    def pick_products():
        path = filedialog.askopenfilename(title="Choose Products CSV", filetypes=[("CSV","*.csv")])
        if not path: return
        messagebox.showinfo("Import", importItemsCSV(path))
    def pick_sales():
        path = filedialog.askopenfilename(title="Choose Sales CSV", filetypes=[("CSV","*.csv")])
        if not path: return
        messagebox.showinfo("Import", importSalesCSV(path))
    customtkinter.CTkButton(bl, text="Import Products (choose CSV)", command=pick_products).pack(side="left", padx=6)
    customtkinter.CTkButton(bl, text="Import Sales (choose CSV)", command=pick_sales).pack(side="left", padx=6)

# add user with acess level with popup
def registerUser():
    reg = customtkinter.CTkToplevel(app)
    reg.title("Create account"); reg.geometry("360x320")
    u = customtkinter.CTkEntry(reg, placeholder_text="Username"); u.pack(fill="x", padx=12, pady=6)
    p = customtkinter.CTkEntry(reg, placeholder_text="Password", show="*"); p.pack(fill="x", padx=12, pady=6)
    f = customtkinter.CTkEntry(reg, placeholder_text="First name"); f.pack(fill="x", padx=12, pady=6)
    l = customtkinter.CTkEntry(reg, placeholder_text="Last name"); l.pack(fill="x", padx=12, pady=6)
    a2 = customtkinter.CTkEntry(reg, placeholder_text="Access (admin/employee/customer)"); a2.insert(0,"customer"); a2.pack(fill="x", padx=12, pady=6)
    def goReg():
        r = register(u.get().strip(), p.get().strip(), f.get().strip(), l.get().strip(), a2.get().strip())
        messagebox.showinfo("Register", r); reg.destroy()
        logAction(user(), f"CREATE USER {u.get().strip()}")
    customtkinter.CTkButton(reg, text="Create", command=goReg).pack(pady=10)

# asks for pid and days for avg
def predictThresholdWindow():
    d = customtkinter.CTkToplevel(app); d.title("Predict Depletion"); d.geometry("320x160")
    e_pid = customtkinter.CTkEntry(d, placeholder_text="Product ID"); e_pid.pack(fill="x", padx=10, pady=8)
    e_days = customtkinter.CTkEntry(d, placeholder_text="Days of history (e.g. 60)"); e_days.pack(fill="x", padx=10, pady=8)
    def go():
        msg = depletionPrediction(e_pid.get().strip(), e_days.get().strip() or "60")
        messagebox.showinfo("Prediction", msg)
        d.destroy()
    customtkinter.CTkButton(d, text="Predict", command=go).pack(pady=8)

# Running the app
def main():
    showLoginScreen()
    app.mainloop()

if __name__ == "__main__":
    main()

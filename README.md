# Inventory Management System

A desktop inventory and sales management app built with Python, CustomTkinter and SQLite. It handles stock control, sales recording, low-stock alerts, sales analytics with charts, simple depletion forecasting, CSV import/export and role-based user accounts.

## Features

- **User accounts with roles**: login and registration with SHA-256 hashed passwords and access levels (admin, employee, customer).
- **Stock control**: add, update and delete products with price, unit cost, quantity, category, storage location and a per-product low-stock threshold.
- **Sales recording**: log sales against products, with stock levels updated automatically.
- **Low-stock alerts**: the dashboard lists every product at or below its restock threshold.
- **Analytics**: daily sales charts (matplotlib) for one product or all products, and rankings by units sold and by revenue over the last N days.
- **Predictive restocking**: estimates how many days until a product runs out, based on its average daily sales.
- **Reports**: filter sales by product and date range, and export them to CSV.
- **CSV import**: bulk-import products and sales, with flexible header matching (for example `qty`, `quantity` and `stock` are all recognised).
- **Audit log**: user actions are recorded with timestamps.

## Tech stack

Python 3, CustomTkinter (GUI), SQLite (storage), matplotlib (charts).

## Getting started

Requires Python 3.9 or later with Tkinter (included with the standard Python installers for Windows and macOS).

```bash
git clone https://github.com/asimsajjad047/inventory-management-system.git
cd inventory-management-system
pip install -r requirements.txt
python inventory_app.py
```

On first run the app creates two SQLite databases next to the script, `accountdb.sqlite3` (users) and `stockdb.sqlite3` (products, sales, audit log, settings), plus a default admin account:

| Username | Password   |
|----------|------------|
| `admin`  | `admin123` |

Change this password, or create your own admin account, before using the app with real data.

## Sample data

The `sample_data/` folder contains CSV files you can load from **Options** in the app.

**Products** (`products_big.csv`, 5,000 products):

```
id,name,price,unitcost,quantity,category,database,low
P00001,Product 00001,23.01,12.78,17,Tools,5,86
```

| Column | Meaning | Also accepted as |
|--------|---------|------------------|
| `id` | Product ID (required) | `productid`, `sku`, `code` |
| `name` | Product name | `productname`, `item`, `title` |
| `price` | Selling price | `unitprice`, `retailprice` |
| `unitcost` | Cost per unit | `cost`, `costprice`, `wholesale` |
| `quantity` | Units in stock | `qty`, `stock`, `onhand` |
| `category` | Category (defaults to General) | `cat`, `type`, `group` |
| `database` | Storage location / bin | `location`, `store`, `bin` |
| `low` | Low-stock threshold | `lowstock`, `reorderlevel`, `threshold` |

Rows whose ID already exists update that product instead of adding a duplicate.

**Sales** (`sales_big.csv`, 20,000 sales; `sales_B8.csv`, a small example for one product):

```
product_id,quantity_sold,sale_price,sale_date
P03298,12,663.63,2025-02-12
```

| Column | Meaning | Also accepted as |
|--------|---------|------------------|
| `product_id` | Product ID (required) | `pid`, `id`, `sku` |
| `quantity_sold` | Units sold | `qty`, `quantity`, `units` |
| `sale_price` | Price per unit | `price`, `unitprice` |
| `sale_date` | `YYYY-MM-DD`, `DD/MM/YYYY` or ISO timestamp (optional, defaults to now) | `date`, `timestamp` |

Import products before sales so the sales match existing product IDs.

# FarmBridge — Farmer-to-Customer Marketplace Demo

## Requirements
- Python 3.10 or newer
- Visual Studio Code
- Python extension for VS Code

## Run on Windows (VS Code terminal)

1. Extract this ZIP file.
2. In VS Code, choose **File → Open Folder** and open the `farmer_marketplace_website` folder.
3. Open **Terminal → New Terminal**.
4. Create a virtual environment:

   ```powershell
   py -m venv .venv
   ```

5. Activate it in PowerShell:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, use Command Prompt terminal and run:

   ```cmd
   .venv\Scripts\activate.bat
   ```

6. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

7. Start the website:

   ```powershell
   python app.py
   ```

8. Open this address in your browser: **http://127.0.0.1:5000**

Keep the terminal open while using the site. Press `Ctrl+C` in the terminal to stop it.

## Demo logins
- Farmer: `farmer@example.com` / `farmer123`
- Customer: `customer@example.com` / `customer123`
- Admin: `admin@farmbridge.local` / `admin123`

You can also register new farmer/customer accounts through the website.

## What is included
- Responsive homepage and product search/filter
- Farmer/customer registration and login
- Farmer product create/edit workflow
- Customer orders and order history
- Farmer order-status updates
- Admin dashboard and seed/packaging supply records
- SQLite database created automatically as `marketplace.db`

## Important demo limitations
This is a local learning prototype, not a production-ready commerce platform. It does not process real payments, provide real delivery tracking, send SMS/email, or verify users. For a public deployment, add secure password hashing, CSRF protection, stronger secret management, proper validation, HTTPS, backups, and a real payment/delivery integration. Demo credentials and plain-text password storage are only for local demonstration; do not deploy as-is.

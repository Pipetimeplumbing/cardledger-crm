# CardLedger — Sports card tracker

A sports and trading card CRM with private owner login and optional $5 USD/month customer workspaces. No Pipe Time files or deployment are changed. See HOSTING.md for Render deployment and Stripe configuration. Paid signups are disabled by default.

## Start

New in v2.0: configure the owner login with **Setup Owner.bat**, or use OWNER_EMAIL and OWNER_PASSWORD securely on your host. Existing records stay in the owner workspace.

### Windows without a command window

After updating to v2.0.0, double-click **Open CardLedger.vbs**. It launches Python in windowless mode, prepares dependencies if necessary, starts the local backend in the background, and opens your browser. First setup needs Internet and can take a few minutes. Errors appear in a dialog; setup/server output is saved to `data/launcher.log`.

Close the browser whenever you want; the backend keeps running until you double-click **Stop CardLedger.vbs** or shut down Windows. Stop it before updating the program. To launch on Windows sign-in, put a shortcut to **Open CardLedger.vbs** in the `shell:startup` folder instead of the BAT shortcut. Use the normal BAT launcher if your Windows configuration blocks scripts. These Windows launchers were syntax/logic checked from Linux but have not been run on Windows here.

Python 3.12 or newer:

For the simplest start, run `python start.py`. It creates an isolated Python environment, installs dependencies if needed, and opens your browser. On Windows, double-click `Start CardLedger.bat` after installing Python. Keep the terminal window open while using the program. Internet is needed for the first dependency installation.

Manual setup:

```sh
python -m venv .venv
# macOS / Linux
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
# Windows: use .venv\Scripts\pip and .venv\Scripts\python instead
```

Open `http://127.0.0.1:3001` on the computer running the program. This is a local address, not a hosted website. The default server listens only on that computer. External Google Fonts are optional; the interface works with local fallback fonts.

## Features

- Card inventory with player, sport, year, set, card number, grade, notes, and quantity.
- Separate subset/parallel, printed card serial number (such as `025/199`), and grading certificate number fields. Identifiers are stored as text to preserve leading zeroes. Use a separate inventory record for each distinct serialized or certified card.
- Categories include Pokémon, Marvel, Disney, and Magic: The Gathering as well as sports. Use card name for the character or card title and Brand / set for the exact release. Existing sports records remain compatible.
- Add purchases and restock. Edit identifying details and manual market estimates.
- Record a sale with optional client, selling fees, shipping, channel, and date; overselling is rejected.
- Exact-cent cost basis accounting: the remaining acquisition cost is allocated proportionally to pieces sold; the final sale consumes any remainder. Restocking adds acquisition cost to the remaining pool. This is weighted average cost, not FIFO or tax reporting.
- Dashboard: pieces in stock, cost basis, estimated market value, all-time revenue, realized profit, and recent monthly performance.
- Searchable client database with contact details, notes, transaction count, and gross spend.
- CRM-style workspace with global search, a contact table, individual contact records and purchase history, customer summaries, dashboard shortcuts, and recent activity.
- **Manage** lets you add and remove custom card categories. Categories used by inventory cannot be removed until those cards are reassigned.
- **Remove stock** subtracts pieces with a reason and records their removed purchase cost. Use **Restock** to add pieces and **Sell** for paid transactions. Removed costs are shown in adjustment history, not deducted from sales-profit metrics.
- **Inventory → Delete** removes a listing and all remaining pieces after confirmation. The underlying record is retained for sales and stock-removal history; sales profit is unchanged. Deleted listings cannot be sold, edited, or restocked. There is no restore button; use a database backup if recovery is needed.
- Open screens on the same backend receive live database updates, normally within about one second, with automatic reconnection. Unsaved form fields are preserved. This is record synchronization, not automatic program installation or a hosted multi-device service.
- **Sales & profit** includes a month selector, monthly transaction/piece/revenue/profit totals, printable receipts, and editable payment method/status. PayPal, Cash App, credit card, cash, and other methods are supported. Save public payment URLs in Manage; receipts open the provider without collecting card details. Paid status is manually recorded, not processor-verified. Recorded revenue includes pending/unpaid sales; it is not a cash-collected report. New sales preserve receipt card/customer snapshots.
- **Manage → Payments & Shopify** provides public payment-link settings, direct per-item or sequential inventory pushes, and CSV export. See `SHOPIFY.md` for required authorization and limitations. Live syncing is not ready until your own store connection is configured and tested.
- Inventory, sales, and clients CSV exports; database backup download.

Market value is manually entered, not a live pricing feed. Profit equals revenue minus allocated card acquisition cost, fees, and shipping; it excludes taxes, refunds, and business overhead. Sales are immutable in this version; there is no refund, void, or edit-sale workflow. Card identifying details in historical views reflect current card metadata.

## Data and backups

## Updating on Windows

Close the running CardLedger command window. Download and fully extract the latest GitHub ZIP into a new folder. Run **Update CardLedger.bat** from that new folder, select your old CardLedger installation folder, and confirm. The helper backs up the old files and data into `.update-backups`, updates program files, and leaves the data folder in place. Restart **Start CardLedger.bat** from your original folder. The sidebar should display **v2.0.0**. Python's standard Tkinter component is needed for the update dialogs (included in normal Windows Python installers).

The launcher now identifies an already-running version and folder, when supported. Close the old command window before launching another copy. The server sends no-store headers so refreshed pages receive updated scripts.

## Database backups

Data persists in `data/collection.sqlite`. Download regular backups from the sidebar and store them securely. To restore, stop the program, preserve the existing database, replace `data/collection.sqlite` with your backup, then restart. CSVs are exports; CSV import is not implemented.

Version 2.0 adds authenticated owner and customer workspaces. Before hosting, configure HTTPS, persistent storage, owner credentials, backups, and billing as described in HOSTING.md. Public customer launch also requires the recovery, verification, support, and policy work listed there. It is not published or connected to the plumbing repository. No demonstration inventory is mixed into real records. Receipt pages are local links, not public customer URLs; print or save them as PDFs to share. Shopify credentials and payment links for the plumbing business are not reused for CardLedger. Your original local inventory is assigned to the owner login; new subscribers receive empty separate databases.

Run validation with `.venv/bin/python -m unittest discover -s tests -v`.

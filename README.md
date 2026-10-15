# CardLedger — Sports card tracker

A separate, local-first inventory, sales, profit, and client database. No Pipe Time files or deployment are changed.

## Start

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
- Categories include Pokémon, Marvel, Disney, and Magic: The Gathering as well as sports. Use card name for the character or card title and Brand / set for the exact release. Existing sports records remain compatible.
- Add purchases and restock. Edit identifying details and manual market estimates.
- Record a sale with optional client, selling fees, shipping, channel, and date; overselling is rejected.
- Exact-cent cost basis accounting: the remaining acquisition cost is allocated proportionally to pieces sold; the final sale consumes any remainder. Restocking adds acquisition cost to the remaining pool. This is weighted average cost, not FIFO or tax reporting.
- Dashboard: pieces in stock, cost basis, estimated market value, all-time revenue, realized profit, and recent monthly performance.
- Searchable client database with contact details, notes, transaction count, and gross spend.
- CRM-style workspace with global search, a contact table, individual contact records and purchase history, customer summaries, dashboard shortcuts, and recent activity.
- Inventory, sales, and clients CSV exports; database backup download.

Market value is manually entered, not a live pricing feed. Profit equals revenue minus allocated card acquisition cost, fees, and shipping; it excludes taxes, refunds, and business overhead. Sales are immutable in this version; there is no refund, void, or edit-sale workflow. Card identifying details in historical views reflect current card metadata.

## Data and backups

## Updating on Windows

Close the running CardLedger command window. Download and fully extract the latest GitHub ZIP into a new folder. Run **Update CardLedger.bat** from that new folder, select your old CardLedger installation folder, and confirm. The helper backs up the old files and data into `.update-backups`, updates program files, and leaves the data folder in place. Restart **Start CardLedger.bat** from your original folder. The sidebar should display **v1.2.0**. Python's standard Tkinter component is needed for the update dialogs (included in normal Windows Python installers).

The launcher now identifies an already-running version and folder, when supported. Close the old command window before launching another copy. The server sends no-store headers so refreshed pages receive updated scripts.

## Database backups

Data persists in `data/collection.sqlite`. Download regular backups from the sidebar and store them securely. To restore, stop the program, preserve the existing database, replace `data/collection.sqlite` with your backup, then restart. CSVs are exports; CSV import is not implemented.

This version is for trusted local use. It has no account login or authorization layer. Do not expose it publicly or deploy it to Render before adding authentication and persistent production storage. It is not published or connected to the plumbing repository. No demonstration inventory is mixed into real records.

Run validation with `.venv/bin/python -m unittest discover -s tests -v`.

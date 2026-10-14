# CardLedger for Google Sheets

Download `CardLedger-Google-Sheets.xlsx` from this folder. On GitHub, open the file and use **Download raw file**. Upload the file to Google Drive, open it with Google Sheets, then choose **File → Save as Google Sheets**.

Start with the **Start Here** tab. Enter purchases in **Inventory**, buyers in **Clients**, and transactions in **Sales**. The **Dashboard** summarizes pieces in stock, inventory purchase cost and manual market value, revenue, profit, and clients.

**Brands & Makes** contains an expandable reference of major card brands, product lines, and historical labels, grouped by collecting family. Inventory column E has a dropdown referencing this list; custom names are allowed with a warning. It is not a complete checklist of every release or a current ownership/licensing directory. Add entries through row 1001. If conversion drops the dropdown, use Google Sheets Data → Data validation → Dropdown from a range with `'Brands & Makes'!A2:A1001` for Inventory E2:E501.

Inventory column C includes sports, Pokémon, Marvel, Disney, and Magic: The Gathering categories. The reference tab includes representative makers and product families for these trading cards, not a full set checklist. Enter the exact release, language, and variant in your record and notes.

Use a different Lot ID for every purchase batch. Do not alter original purchase costs after selling from a lot. Sales deduct quantity from the matching lot; a multi-lot sale needs separate rows with fees divided between them. The worksheet flags mistakes but does not prevent concurrent users from overselling stock.

This workbook is a separate spreadsheet template, not a live sync with the web application's database. It contains no client data or sample transactions. All values are in USD. Profit excludes taxes, returns, and overhead. Input capacity is 500 rows per tab. Formula cells are blue; protect them after Google Sheets conversion.

To regenerate the workbook, install `openpyxl` and run `python spreadsheet/build_template.py` from the repository root. Google account import and live formula recalculation have not been verified in this session.

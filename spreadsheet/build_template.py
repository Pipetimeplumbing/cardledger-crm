from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule
from brands import catalog

ROOT=Path(__file__).parent
LIMIT=501
wb=Workbook()
dashboard=wb.active;dashboard.title='Dashboard'
inventory=wb.create_sheet('Inventory');sales=wb.create_sheet('Sales');clients=wb.create_sheet('Clients');guide=wb.create_sheet('Start Here')
brands=wb.create_sheet('Brands & Makes')
navy='17243B';blue='5168E8';muted='77849A';pale='EFF2FF';green='249779';red='FCE7E7'
currency='"$"#,##0.00;[Red]("$"#,##0.00)'
headers={
 'Inventory':['Lot ID','Player / Character / Card','Card category','Year','Brand / Set','Card #','Grade','Pieces purchased','Purchase cost / card','Est. value / card','Pieces sold','Pieces in stock','Inventory cost value','Est. inventory value','Notes','Check','Subset / parallel','Card serial number','Grading certificate #'],
 'Sales':['Sale date','Sale ID','Lot ID','Client ID (optional)','Quantity sold','Sale price / card','Revenue','Cost / card','Cost basis','Total fees','Total shipping','Profit','Channel','Notes','Player / Card','Client name','Check'],
 'Clients':['Client ID','Client name','Email','Phone','Notes','Sale count','Total spending','Check']}

def prepare(sheet):
    sheet.append(headers[sheet.title]);sheet.freeze_panes='C2';sheet.auto_filter.ref=f'A1:{sheet.cell(1,sheet.max_column).column_letter}{LIMIT}'
    sheet.sheet_view.showGridLines=False;sheet.row_dimensions[1].height=34
    for c in sheet[1]:c.fill=PatternFill('solid',fgColor=navy);c.font=Font(color='FFFFFF',bold=True,size=10);c.alignment=Alignment(vertical='center',wrap_text=True)
    for col in range(1,sheet.max_column+1):sheet.column_dimensions[sheet.cell(1,col).column_letter].width=21
    for row in range(2,LIMIT+1):
        sheet.row_dimensions[row].height=23
        for col in range(1,sheet.max_column+1):
            c=sheet.cell(row,col);c.font=Font(name='Calibri',size=11,color=navy);c.fill=PatternFill('solid',fgColor='FFFFFF' if row%2 else 'F8FAFD')
    sheet.print_title_rows='1:1'

def formula(sheet,row,col,value,money=False):
    c=sheet.cell(row,col,value);c.fill=PatternFill('solid',fgColor=pale);c.font=Font(name='Calibri',size=11,color=blue)
    if money:c.number_format=currency

def validate(sheet,column,kind='decimal',minimum=0):
    rule=DataValidation(type=kind,operator='greaterThanOrEqual',formula1=str(minimum),allow_blank=True)
    rule.errorTitle='Check this value';rule.error='Enter a valid non-negative amount or whole-number quantity.';rule.showErrorMessage=True;rule.errorStyle='stop'
    sheet.add_data_validation(rule);rule.add(f'{column}2:{column}{LIMIT}')

for sheet in (inventory,sales,clients):prepare(sheet)
brands.append(['Brand / product name','Brand family / make','Category','Reference notes'])
for row in catalog():brands.append(row)
brands.freeze_panes='A2';brands.auto_filter.ref=f'A1:D{brands.max_row}';brands.sheet_view.showGridLines=False
for column,width in [('A',38),('B',26),('C',34),('D',85)]:brands.column_dimensions[column].width=width
for cell in brands[1]:
    cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor=navy)
for row in brands.iter_rows(min_row=2):
    for cell in row:
        cell.font=Font(size=11,color=navy);cell.alignment=Alignment(wrap_text=True,vertical='center')
        cell.fill=PatternFill('solid',fgColor='FFFFFF' if cell.row%2 else 'F8FAFD')
brand_rule=DataValidation(type='list',formula1='INDIRECT("\'Brands & Makes\'!$A$2:$A$1001")',allow_blank=True)
brand_rule.showErrorMessage=True;brand_rule.errorStyle='warning';brand_rule.errorTitle='Custom brand';brand_rule.error='This brand is not in the reference list. You may keep it or add it to Brands & Makes.'
brand_rule.showInputMessage=True;brand_rule.promptTitle='Brand or product line';brand_rule.prompt='Choose a listed brand, or enter a custom release.'
inventory.add_data_validation(brand_rule);brand_rule.add(f'E2:E{LIMIT}')
for r in range(2,LIMIT+1):
    formula(inventory,r,11,f'=IF(A{r}="","",SUMIF(Sales!$C$2:$C${LIMIT},A{r},Sales!$E$2:$E${LIMIT}))')
    formula(inventory,r,12,f'=IF(A{r}="","",H{r}-K{r})')
    formula(inventory,r,13,f'=IF(A{r}="","",ROUND(L{r}*I{r},2))',True)
    formula(inventory,r,14,f'=IF(A{r}="","",ROUND(L{r}*J{r},2))',True)
    formula(inventory,r,16,f'=IF(A{r}="","",IF(COUNTIF($A$2:$A${LIMIT},A{r})>1,"Duplicate lot ID",IF(OR(B{r}="",H{r}="",I{r}="",J{r}=""),"Complete required fields",IF(L{r}<0,"OVER SOLD","OK"))))')
    formula(sales,r,7,f'=IF(C{r}="","",ROUND(E{r}*F{r},2))',True)
    formula(sales,r,8,f'=IF(C{r}="","",IFERROR(VLOOKUP(C{r},Inventory!$A$2:$J${LIMIT},9,FALSE),0))',True)
    formula(sales,r,9,f'=IF(C{r}="","",ROUND(E{r}*H{r},2))',True)
    formula(sales,r,12,f'=IF(C{r}="","",ROUND(G{r}-I{r}-J{r}-K{r},2))',True)
    formula(sales,r,15,f'=IF(C{r}="","",IFERROR(VLOOKUP(C{r},Inventory!$A$2:$B${LIMIT},2,FALSE),"Unknown lot"))')
    formula(sales,r,16,f'=IF(D{r}="","",IFERROR(VLOOKUP(D{r},Clients!$A$2:$B${LIMIT},2,FALSE),"Unknown client"))')
    formula(sales,r,17,f'=IF(C{r}="","",IF(COUNTIF(Inventory!$A$2:$A${LIMIT},C{r})<>1,"Check lot ID",IF(OR(A{r}="",B{r}="",E{r}="",F{r}=""),"Complete required fields",IF(COUNTIF($B$2:$B${LIMIT},B{r})>1,"Duplicate sale ID",IF(AND(D{r}<>"",COUNTIF(Clients!$A$2:$A${LIMIT},D{r})<>1),"Check client ID",IF(VLOOKUP(C{r},Inventory!$A$2:$L${LIMIT},12,FALSE)<0,"OVER SOLD","OK"))))))')
    formula(clients,r,6,f'=IF(A{r}="","",COUNTIF(Sales!$D$2:$D${LIMIT},A{r}))')
    formula(clients,r,7,f'=IF(A{r}="","",SUMIF(Sales!$D$2:$D${LIMIT},A{r},Sales!$G$2:$G${LIMIT}))',True)
    formula(clients,r,8,f'=IF(A{r}="","",IF(COUNTIF($A$2:$A${LIMIT},A{r})>1,"Duplicate client ID",IF(B{r}="","Add client name","OK")))')
    for col in (9,10):inventory.cell(r,col).number_format=currency
    for col in (6,10,11):sales.cell(r,col).number_format=currency
    sales.cell(r,1).number_format='yyyy-mm-dd'
    for sheet,cols in ((inventory,(1,6,17,18,19)),(sales,(2,3,4)),(clients,(1,4))):
        for col in cols:sheet.cell(r,col).number_format='@'

category_rule=DataValidation(type='list',formula1='"Baseball,Basketball,Football,Hockey,Soccer,Pokémon,Marvel,Disney,Magic: The Gathering,Other"',allow_blank=True)
category_rule.showErrorMessage=True;category_rule.errorStyle='warning';category_rule.error='Choose a card category or keep a custom category.'
inventory.add_data_validation(category_rule);category_rule.add(f'C2:C{LIMIT}')
validate(inventory,'H','whole',1)
for col in ('I','J'):validate(inventory,col)
validate(sales,'E','whole',1)
for col in ('F','J','K'):validate(sales,col)
date_rule=DataValidation(type='date',operator='between',formula1='DATE(1900,1,1)',formula2='TODAY()',allow_blank=True)
date_rule.showErrorMessage=True;date_rule.error='Enter a valid sale date that is not in the future.';sales.add_data_validation(date_rule);date_rule.add(f'A2:A{LIMIT}')
for sheet,column in ((sales,'C'),(sales,'D')):
    target='Inventory' if column=='C' else 'Clients'
    rule=DataValidation(type='list',formula1=f'INDIRECT("\'{target}\'!$A$2:$A${LIMIT}")',allow_blank=True)
    rule.showErrorMessage=True;rule.error='Choose an existing ID.';sheet.add_data_validation(rule);rule.add(f'{column}2:{column}{LIMIT}')
inventory.conditional_formatting.add(f'L2:L{LIMIT}',CellIsRule(operator='lessThan',formula=['0'],fill=PatternFill('solid',fgColor=red)))
sales.conditional_formatting.add(f'L2:L{LIMIT}',CellIsRule(operator='lessThan',formula=['0'],font=Font(color='BE4141')))

dashboard.sheet_view.showGridLines=False;dashboard.column_dimensions['A'].width=4;dashboard.column_dimensions['B'].width=32;dashboard.column_dimensions['C'].width=25;dashboard.column_dimensions['D'].width=4;dashboard.column_dimensions['E'].width=28;dashboard.column_dimensions['F'].width=22
dashboard.merge_cells('B2:F2');dashboard['B2']='CARDLEDGER  |  COLLECTION CRM';dashboard['B2'].font=Font(size=22,bold=True,color=navy);dashboard.row_dimensions[2].height=40
dashboard.merge_cells('B3:F3');dashboard['B3']='Inventory, customers, sales, and profit in one workbook.';dashboard['B3'].font=Font(color=muted,size=11)
metrics=[('Pieces in stock',f'=SUM(Inventory!L2:L{LIMIT})',False),('Inventory purchase-cost value',f'=SUM(Inventory!M2:M{LIMIT})',True),('Estimated inventory market value',f'=SUM(Inventory!N2:N{LIMIT})',True),('Sales revenue',f'=SUM(Sales!G2:G{LIMIT})',True),('Realized profit',f'=SUM(Sales!L2:L{LIMIT})',True),('Pieces sold',f'=SUM(Sales!E2:E{LIMIT})',False),('Clients',f'=COUNTA(Clients!A2:A{LIMIT})',False),('Inventory / sales check flags',f'=COUNTIF(Inventory!P2:P{LIMIT},"?*")-COUNTIF(Inventory!P2:P{LIMIT},"OK")+COUNTIF(Sales!Q2:Q{LIMIT},"?*")-COUNTIF(Sales!Q2:Q{LIMIT},"OK")+COUNTIF(Clients!H2:H{LIMIT},"?*")-COUNTIF(Clients!H2:H{LIMIT},"OK")',False)]
for row,(label,value,is_money) in enumerate(metrics,6):
    dashboard.cell(row,2,label).font=Font(color=navy,size=12)
    cell=dashboard.cell(row,3,value);cell.font=Font(color=blue,size=16,bold=True);cell.fill=PatternFill('solid',fgColor=pale);cell.number_format=currency if is_money else '#,##0';dashboard.row_dimensions[row].height=32
dashboard.merge_cells('B16:F16');dashboard['B16']='Profit = revenue − card cost − fees − shipping. Excludes taxes and overhead.';dashboard['B16'].font=Font(color=muted,size=10)
dashboard.merge_cells('B18:F18');dashboard['B18']='Blue cells contain formulas. Enter data in the white cells on each tab.';dashboard['B18'].font=Font(color=blue,size=10)
guide.column_dimensions['A'].width=5;guide.column_dimensions['B'].width=105;guide.sheet_view.showGridLines=False
instructions=[
 'CARDLEDGER — GOOGLE SHEETS QUICK START',
 'Upload this XLSX to Google Drive. Right-click → Open with → Google Sheets, then File → Save as Google Sheets.',
 '1. Inventory: use one unique Lot ID per purchase batch (example LOT-001). Enter player or character, card category, pieces purchased, purchase cost per card, and estimated market value per card.',
 '2. Restocking: add a NEW inventory row with a NEW Lot ID for each purchase batch. Do not increase old purchase quantities or change old purchase costs after recording sales.',
 '3. Clients: assign unique Client IDs (example CLI-001), then enter names, email, phone, and notes.',
 '4. Sales: enter date, unique Sale ID (SALE-001), Lot ID, optional Client ID, quantity, sale price per card, total fees, and total shipping. Formula columns calculate revenue, cost, profit, names, and checks.',
 '5. A sale spanning multiple lots must use one Sales row per lot, each with a unique Sale ID. Divide fees and shipping across those rows; do not count them twice.',
 '6. Dashboard updates automatically. Check flags must be resolved before relying on totals. Overselling is flagged, but spreadsheets do not prevent simultaneous users from selling the same stock.',
 '7. Dollar amounts are USD. Purchase costs should include acquisition costs allocated per card. Inventory market estimates are manually entered, not live prices.',
 '8. Client spending is gross sale revenue, not net profit. Inventory price estimates can be changed; historical purchase cost must stay fixed to preserve sales profit.',
 '9. This template supports 500 input rows per tab. To expand it, copy formulas and validation downward AND extend all ranges in formulas and dropdowns.',
 '10. Blue cells are formulas; do not type over them. After converting to Google Sheets, use Data → Protect sheets and ranges to protect formula columns.',
 '11. Inventory formulas: pieces in stock = pieces purchased − pieces sold. Profit = quantity × sale price − quantity × original lot cost − fees − shipping.',
 '12. Keep Drive sharing restricted because the workbook contains client contact information. Use Google Sheets version history and regular exports for backups.',
 '13. Correct mistakes by editing the original entry. There is no refund, return, tax, or automated card-pricing integration in this workbook.',
 '14. Google Sheets may change validation presentation during conversion. Verify dropdowns and formulas after import. This file was generated and structurally validated; Google Sheets import has not been tested in a connected account.',
 '15. Brands & Makes lists major brands, product lines, and historical labels; it is not an exhaustive release checklist or a current ownership/licensing directory. Inventory column E includes a dropdown. Add missing names in column A of Brands & Makes (up to row 1001) or enter a custom name.',
 '17. Inventory Q is Subset / parallel, R is card serial number (e.g. 025/199), and S is grading certificate number. Grade remains in column G. Keep separate serialized or certified cards in separate rows.',
 '16. In Google Sheets, if the brand dropdown does not convert, select Inventory E2:E501 → Data → Data validation → Dropdown from a range → Brands & Makes!A2:A1001. Use a warning rather than rejecting custom brands.'
]
for r,line in enumerate(instructions,2):
    c=guide.cell(r,2,line);c.font=Font(name='Calibri',size=12 if r==2 else 11,color=navy,bold=r==2);c.alignment=Alignment(wrap_text=True,vertical='center');guide.row_dimensions[r].height=45 if r>2 else 32
wb.active=wb.sheetnames.index('Start Here')
wb.calculation.fullCalcOnLoad=True
path=ROOT/'CardLedger-Google-Sheets.xlsx';wb.save(path)
check=load_workbook(path)
assert check['Sales']['L2'].value=='=IF(C2="","",ROUND(G2-I2-J2-K2,2))'
assert check['Inventory']['L2'].value=='=IF(A2="","",H2-K2)'
assert len(check.sheetnames)==6
print(f'Created {path.name}: 6 tabs, {len(catalog())} brand/product labels, 500 rows per input tab.')

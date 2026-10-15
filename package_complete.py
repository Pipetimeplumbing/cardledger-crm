"""Build the distributable without databases, secrets, caches, or older ZIPs."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import subprocess

root=Path(__file__).parent
output=root/'downloads'/'CardLedger-Complete.zip'
output.parent.mkdir(exist_ok=True)
files=subprocess.run(['git','-C',str(root),'ls-files','-z'],capture_output=True,check=True).stdout.decode().split('\0')
with ZipFile(output,'w',ZIP_DEFLATED) as bundle:
    for name in files:
        if not name:continue
        relative=Path(name)
        if relative.suffix.lower()=='.zip' or any(part in ('data','.venv','.git','__pycache__','.update-backups','downloads') for part in relative.parts):continue
        if relative.name.startswith('.env'):continue
        path=root/relative
        if path.is_file() and not path.is_symlink():bundle.write(path,Path('CardLedger')/relative)
with ZipFile(output) as bundle:
    assert bundle.testzip() is None
    names=bundle.namelist()
    for required in ('app.py','accounts.py','subscriptions.py','Open CardLedger.vbs','Setup Owner.bat','START HERE.txt','templates/receipt.html','spreadsheet/CardLedger-Google-Sheets.xlsx'):
        assert 'CardLedger/'+required in names,required
    assert not any(Path(name).suffix in ('.sqlite','.db') for name in names)
print(f'Created and verified {output.name} ({output.stat().st_size:,} bytes).')

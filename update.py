"""Run from a freshly extracted download to update an existing installation."""
import shutil
from datetime import datetime
from pathlib import Path
import os
import urllib.request

FILES=('app.py','start.py','update.py','requirements.txt','README.md','.gitignore','Start CardLedger.bat','Update CardLedger.bat')
DIRECTORIES=('public','spreadsheet')

def install(source,target):
    source,target=Path(source).resolve(),Path(target).resolve()
    if source==target:
        raise ValueError('Select your OLD CardLedger folder, not this new download.')
    if not (target/'app.py').is_file():
        raise ValueError('Select the CardLedger folder containing app.py and Start CardLedger.bat.')
    if not (source/'public'/'app.js').is_file():
        raise ValueError('Extract the entire new ZIP before running the updater.')
    entries=[Path(name) for name in FILES if (source/name).is_file()]
    for name in DIRECTORIES:
        entries.extend(path.relative_to(source) for path in (source/name).rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    for relative in entries:
        if (source/relative).is_symlink() or (target/relative).is_symlink():
            raise ValueError('Update folders must contain ordinary files, not symbolic links.')
        if not (target/relative).resolve().is_relative_to(target):
            raise ValueError('An update destination points outside the installation.')
    backup=target/'.update-backups'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True)
    if (target/'data').exists():shutil.copytree(target/'data',backup/'data')
    old=[];added=[]
    for relative in entries:
        dest=target/relative
        if dest.is_file():
            (backup/relative).parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dest,backup/relative);old.append(relative)
        else:added.append(relative)
    try:
        for relative in entries:
            (target/relative).parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source/relative,target/relative)
    except Exception:
        for relative in old:shutil.copy2(backup/relative,target/relative)
        for relative in added:(target/relative).unlink(missing_ok=True)
        raise
    return backup

def main():
    import tkinter as tk
    from tkinter import filedialog,messagebox
    window=tk.Tk();window.withdraw()
    try:
        port=os.environ.get('PORT','3001')
        try:urllib.request.urlopen(f'http://127.0.0.1:{port}',timeout=1).close()
        except Exception:pass
        else:raise ValueError('Close the running CardLedger command window before updating.')
        messagebox.showinfo('Update CardLedger','Select your OLD CardLedger folder. Your data will be preserved and backed up.')
        chosen=filedialog.askdirectory(title='Select your OLD CardLedger installation folder')
        if not chosen:return
        if not messagebox.askyesno('Confirm update',f'Update this folder?\n{chosen}\nYour data folder will be kept.'):
            return
        backup=install(Path(__file__).parent,chosen)
        messagebox.showinfo('Update complete',f'Updated to CardLedger v1.2.0.\nBackup: {backup}\nOpen Start CardLedger.bat in your original folder.')
    except Exception as error:messagebox.showerror('Unable to update',str(error))
    finally:window.destroy()

if __name__=='__main__':main()

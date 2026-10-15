"""Windows background start/stop entry point. No terminal is required."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT=Path(__file__).resolve().parent
PORT=os.environ.get('PORT','3001')
URL=f'http://127.0.0.1:{PORT}'
FLAGS=getattr(subprocess,'CREATE_NO_WINDOW',0)

def message(text,error=False):
    if os.name=='nt':ctypes.windll.user32.MessageBoxW(0,text,'CardLedger',16 if error else 64)

def running():
    try:
        with urllib.request.urlopen(URL+'/api/version',timeout=2) as response:return json.load(response)
    except Exception:return None

def is_our_copy(info):
    return bool(info and os.path.normcase(str(Path(info.get('folder','')).resolve()))==os.path.normcase(str(ROOT)))

def main():
    info=running()
    if '--stop' in sys.argv:
        if not info:message('CardLedger is already stopped.');return
        if not is_our_copy(info):raise ValueError('A different CardLedger folder is running. Use its Stop CardLedger file.')
        if not info.get('pid'):raise ValueError('This older copy must be stopped by closing its command window.')
        result=subprocess.run(['taskkill','/PID',str(info['pid']),'/F'],creationflags=FLAGS,capture_output=True)
        if result.returncode:raise ValueError('Unable to stop CardLedger. Check Windows Task Manager.')
        message('CardLedger stopped. Your saved data is kept.');return
    if info:
        if not is_our_copy(info):raise ValueError('Another CardLedger folder is running. Stop that copy before opening this one.\nRunning folder: '+info.get('folder','unknown'))
        webbrowser.open(URL);return
    ROOT.joinpath('data').mkdir(exist_ok=True)
    python=ROOT/'.venv'/'Scripts'/'python.exe'
    log_path=ROOT/'data'/'launcher.log'
    with log_path.open('a',encoding='utf-8') as log:
        if not python.exists():
            subprocess.run([sys.executable,'-m','venv',str(ROOT/'.venv')],check=True,creationflags=FLAGS,stdout=log,stderr=log)
        if subprocess.run([str(python),'-c','import flask'],creationflags=FLAGS,stdout=log,stderr=log).returncode:
            subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'requirements.txt')],check=True,creationflags=FLAGS,stdout=log,stderr=log)
        process=subprocess.Popen([str(python),str(ROOT/'app.py')],cwd=ROOT,creationflags=FLAGS,stdout=log,stderr=log,stdin=subprocess.DEVNULL)
        for _ in range(80):
            if process.poll() is not None:raise ValueError(f'CardLedger could not start. See {log_path}')
            info=running()
            if is_our_copy(info) and info.get('pid')==process.pid:
                webbrowser.open(URL);return
            time.sleep(.25)
        process.terminate()
        raise ValueError(f'CardLedger did not start in time. See {log_path}')

if __name__=='__main__':
    try:main()
    except Exception as error:message(str(error),True)

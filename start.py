"""Run with `python start.py` to install dependencies and open CardLedger."""
import os
import json
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

root=Path(__file__).parent
environment=root/'.venv'
python=environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if not python.exists():
    print('Creating the CardLedger Python environment…',flush=True)
    venv.create(environment,with_pip=True)
if subprocess.run([str(python),'-c','import flask'],capture_output=True).returncode:
    subprocess.run([str(python),'-m','pip','install','-r',str(root/'requirements.txt')],check=True)
port=os.environ.get('PORT','3001')
url=f'http://127.0.0.1:{port}'
try:
    urllib.request.urlopen(url,timeout=1).close()
except Exception:
    pass
else:
    try:
        with urllib.request.urlopen(url+'/api/version',timeout=2) as response:
            running=json.load(response)
        details=f'Running version: {running.get("version", "unknown")}\nRunning folder: {running.get("folder", "unknown")}'
    except Exception:
        details='An older CardLedger copy or another program is already running.'
    sys.exit(f'{details}\nClose its command window before starting this copy.\nThe copy you tried to start is: {root.resolve()}')
process=subprocess.Popen([str(python),str(root/'app.py')],cwd=root)
try:
    for _ in range(40):
        if process.poll() is not None:
            sys.exit('The server could not start. Read the error above.')
        try:
            urllib.request.urlopen(url+'/api/state',timeout=1).close()
            break
        except Exception:time.sleep(0.25)
    else:
        sys.exit('The server did not become ready. Read the error above.')
    print(f'CardLedger v1.2.0\nFolder: {root.resolve()}\nRunning at {url}. Keep this window open. Press Ctrl+C to stop.',flush=True)
    webbrowser.open(url)
    process.wait()
except KeyboardInterrupt:
    pass
finally:
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=10)

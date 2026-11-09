#!/usr/bin/env python3
"""Build and verify the local MuseEditor test candidate without modifying originals."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'build' / 'tonight-r2'

def run(*args):
    result = subprocess.run([sys.executable, *args], cwd=ROOT,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'},
                            text=True, capture_output=True)
    print(result.stdout, end='')
    print(result.stderr, end='', file=sys.stderr)
    result.check_returncode()
    return result.stdout + result.stderr

def main():
    log = run('test_muse_tonight.py')
    run('generate_device.py', '--output-dir', str(OUT))
    run('render_preview.py')
    shutil.copyfile(ROOT/'TONIGHT_GUIDE.md', OUT/'READ_ME_FIRST.md')
    (OUT/'TEST_RESULTS.txt').write_text(log)
    patch = json.loads((OUT/'MuseEditor Tonight r2.maxpat').read_text())
    blob = (OUT/'MuseEditor Tonight r2.amxd').read_bytes()
    embedded = json.loads(blob[blob.index(b'{'):blob.rindex(b'}')+1])
    assert embedded == patch, 'Packaged device differs from generated patch'
    import generate_device as G
    assert G.build().to_maxpat() == patch, 'Build differs from generator'
    assert blob == G.build_amxd(patch,'mmmm','MuseEditor Tonight r2.amxd')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {
        'candidate': 'MuseEditor Tonight r2 2026-10-24',
        'upstream_commit': '6cb85cb271b367dc57fca7062be9c27e6b9171f2',
        'validation': '12 graph-level tests; AMXD/JSON/generator equality; r2 switch clicks verified in Live 12 Beta; no hardware/MIDI capture test',
        'source_sha256': {name:sha(ROOT/name) for name in [
            'generate_device.py','render_preview.py','test_muse_tonight.py',
            'build_tonight.py','TONIGHT_GUIDE.md','Muse_MIDI_CCs.csv']},
        'files_sha256': {p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='BUILD_MANIFEST.json'},
    }
    (OUT/'BUILD_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    archive=OUT.parent/'MuseEditor-Tonight-r2-2026-10-24.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.iterdir()):
            if p.is_file():z.write(p,'MuseEditor Tonight r2/'+p.name)
    print('Verified package:', archive)
    print('SHA256:', sha(archive))

if __name__=='__main__':main()

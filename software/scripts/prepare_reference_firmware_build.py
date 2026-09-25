"""Stage hash-pinned source and guarded servo library for compile-only review.

Never extracts binaries, invokes Arduino, opens devices or overwrites differing
existing files. Staging is not a deployment-ready firmware release.
"""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile


def archive(url,digest):
    with urllib.request.urlopen(url,timeout=20) as response:raw=response.read(16_000_001)
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Source archive mismatch')
    return zipfile.ZipFile(io.BytesIO(raw))


def publish(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=raw:raise ValueError('Existing staging file differs; refusing overwrite')
    else:
        with path.open('xb') as stream:stream.write(raw)


def main():
    root=Path(__file__).resolve().parents[1]/'.firmware-tools'
    staged={}
    with archive('https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example20260115.zip',
        'd627e180c4814776ef0ccf78f237482d48dcd3745be1e37378c25fd9005fd6a9') as z:
        prefix='RoArm-M3_example20260115/RoArm-M3_example/'
        for name in z.namelist():
            relative=name.removeprefix(prefix)
            if not name.startswith(prefix) or '/' in relative or not relative.endswith(('.h','.ino')):continue
            raw=z.read(name);destination=root/'reference'/'RoArm-M3_example'/relative
            publish(destination,raw);staged[str(destination.relative_to(root))]=hashlib.sha256(raw).hexdigest()
    with archive('https://files.waveshare.com/upload/5/5a/SERVO_DRIVER_WITH_ESP32.zip',
        'b8b377642b3eb45610226fdf96fbc61d7c012a512bdd7f8c904a9c1ac88328af') as z:
        for name in z.namelist():
            relative=name.removeprefix('SCServo/')
            if not name.startswith('SCServo/') or '/' in relative or not relative.endswith(('.h','.cpp')):continue
            raw=z.read(name)
            if relative=='SCS.cpp':
                text=raw.decode('utf-8-sig').replace('\r\r\n','\n').replace('\r\n','\n')
                anchor='\tint Size = readSCS(nData, nLen);'
                if text.count(anchor)!=1:raise ValueError('Ambiguous guard insertion')
                raw=text.replace(anchor,'\tif(bBuf[0]!=ID || bBuf[1]!=(unsigned int)nLen+2){ return 0; }\n'+anchor).encode()
            destination=root/'user'/'libraries'/'SCServo'/relative
            publish(destination,raw);staged[str(destination.relative_to(root))]=hashlib.sha256(raw).hexdigest()
    report=dict(schema='rocell.reference_build_inputs.v1',files=staged,
        source_identity='REFERENCE_NOT_INSTALLED',deployable=False,firmware_uploaded=False)
    publish(root/'reference-build-inputs.json',json.dumps(report,indent=2,sort_keys=True).encode())
    print(json.dumps(dict(staged_files=len(staged),manifest=str(root/'reference-build-inputs.json'))))


if __name__=='__main__':main()

"""Original-byte checks for the offline zero comparison; no hardware."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from review_zero_variability import original_fields


def sample(body):
    raw=json.dumps(body).encode()
    return dict(response_base64=base64.b64encode(raw).decode(),
        response_bytes=len(raw),response_sha256=hashlib.sha256(raw).hexdigest())


def test_raw_negative_and_zero_preserved_missing_not_zero():
    result=original_fields(sample(dict(tR=-28,tB=0)))
    assert result==dict(tB=0,tS=None,tE=None,tT=None,tR=-28)


@pytest.mark.parametrize('field,value',[('response_bytes',0),('response_sha256','0'*64)])
def test_changed_original_rejected(field,value):
    record=sample(dict(tR=-20));record[field]=value
    with pytest.raises(ValueError):original_fields(record)

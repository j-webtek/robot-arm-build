"""Read current correction source and bounded original reference files."""
from pathlib import Path
from .wizard_diagnostic_coordinator import source_fingerprint,decode_diagnostic_json
from .physical_onboarding_durability import safe_root,contained_path,read_bounded_regular_file
from rocell.providers.windows.wrist_correction_current_context import WristCorrectionContextRequest
from rocell.providers.windows.wrist_correction_native_protocol import digest,require

ORIGINAL_FILES={'runtime_sha256':'runtime.original.json',
    'protocol_review_sha256':'protocol.original.json','native_controller_review_sha256':'controller.original.json'}


class WristCorrectionReferenceReader:
    def __init__(self,request,*,workspace,root):
        require(type(request) is WristCorrectionContextRequest,'Exact correction request required')
        self._request=request
        self._workspace=safe_root(Path(workspace))
        self._directory=contained_path(safe_root(root),request.to_dict()['attempt_id']+
            '-wrist-correction-native-child',label='correction reference directory')

    def original(self,reference):
        require(reference in ORIGINAL_FILES,'Unknown correction reference')
        raw=read_bounded_regular_file(contained_path(safe_root(self._directory),ORIGINAL_FILES[reference],
            label='correction reference original'),maximum_bytes=128*1024)
        value=decode_diagnostic_json(raw,maximum=128*1024)
        require(type(value) is dict and bool(value) and digest(raw)==self._request.to_dict()['references'][reference],
            'Correction reference original changed')
        return raw

    def __call__(self):
        refs={'source_sha256':source_fingerprint(self._workspace)}
        refs.update((key,digest(self.original(key))) for key in ORIGINAL_FILES)
        require(refs==self._request.to_dict()['references'],'Correction source/reference mismatch')
        return tuple(sorted(refs.items()))


class FrozenWristCorrectionReferences:
    """Snapshot after repeated source checks, never a current USB assertion."""
    def __init__(self,reader):
        require(type(reader) is WristCorrectionReferenceReader,'Exact correction reference reader required')
        refs=reader()
        originals=tuple((key,reader.original(key)) for key in sorted(ORIGINAL_FILES))
        require(reader()==refs,'Correction references changed during freeze')
        self._refs,self._originals=refs,originals

    def __call__(self):
        return self._refs

    def original(self,key):
        return dict(self._originals)[key]

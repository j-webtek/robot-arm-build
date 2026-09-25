"""Current-user DPAPI storage for the coordinator's bench review authority.

No import-time provisioning, UI prompt, plaintext file, key export or automatic
replacement. The host supplies a trusted private root outside diagnostic exports.
DPAPI is not isolation from other code running as the same Windows user.
"""

import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import secrets

from rocell.application.physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file,
    _reject_unsafe_component,
)
from rocell.safety.bench_review_authority import BenchReviewAuthority

FILENAME = 'local-bench-review-v1.dpapi'
_DOMAIN = b'rocell.local-bench-review-v1\x00'
_ENTROPY = b'rocell.bench-review-key.current-user.v1'
MAX_BLOB = 16384


class BenchKeyProtectionError(RuntimeError):
    """Bounded native error metadata; never includes key/blob contents."""
    def __init__(self, winerror):
        self.winerror = winerror
        super().__init__('DPAPI operation failed')


def _local_base():
    if os.name!='nt': raise ValueError('Bench key setup requires Windows')
    # The owned worker intentionally inherits only SystemRoot. Query the
    # current-user known folder; do not weaken that boundary by copying home
    # variables or assuming the user's profile lives at a conventional path.
    # FOLDERID_LocalAppData, GUID in native little-endian field layout.
    folder = (C.c_ubyte*16).from_buffer_copy(bytes.fromhex('8527b3f1ba6fcf4f9d557b8e7f157091'))
    shell = C.WinDLL('shell32', use_last_error=True)
    ole = C.WinDLL('ole32', use_last_error=True)
    shell.SHGetKnownFolderPath.argtypes = [C.c_void_p, W.DWORD, W.HANDLE, C.POINTER(C.c_void_p)]
    shell.SHGetKnownFolderPath.restype = C.c_long
    ole.CoTaskMemFree.argtypes = [C.c_void_p]
    ole.CoTaskMemFree.restype = None
    output = C.c_void_p()
    try:
        # Flags zero: retrieve the current location, without creating folders.
        result = shell.SHGetKnownFolderPath(C.byref(folder), 0, None, C.byref(output))
        if result != 0 or not output.value:
            raise RuntimeError('Current-user LocalAppData lookup failed')
        return safe_root(Path(C.wstring_at(output)))
    finally:
        if output.value:
            ole.CoTaskMemFree(output)


def host_key_root(workspace, *, create=False):
    """Shared host/child location; loading never creates missing directories."""
    if type(create) is not bool: raise ValueError('Explicit create flag required')
    root = base = _local_base()
    workspace = Path(workspace).resolve(strict=True)
    if root==workspace or workspace in root.parents:
        raise ValueError('Private key storage cannot be inside the workspace')
    for component in ('RoCell','private','bench-review-v1'):
        candidate = root/component
        if not candidate.exists():
            if not create: return None
            candidate.mkdir()
        # Packaged Windows processes can virtualize newly created AppData
        # folders without a filesystem reparse point. Check the logical child
        # before resolving it, then validate every physical path component.
        # Never generalize this exception to arbitrary durability/export roots.
        _reject_unsafe_component(candidate, 'private review directory')
        resolved = candidate.resolve(strict=True)
        if (base not in resolved.parents or resolved == workspace
                or workspace in resolved.parents):
            raise ValueError('Private review directory escaped local storage')
        root = safe_root(resolved)
    return root


def load_host_bench_review_authority(workspace):
    root = host_key_root(workspace)
    if root is None: raise ValueError('Private bench review key is not configured')
    return load_bench_review_authority(root)


def load_host_first_motion_review_authority(workspace):
    """Reuse protected storage with a separate derived domain; no provisioning."""
    return load_host_bench_review_authority(workspace).for_first_motion()


class _Blob(C.Structure):
    _fields_ = [('size',W.DWORD),('data',C.POINTER(C.c_ubyte))]


def load_host_observational_review_authority(workspace):
    """Read existing protected storage; never provision or replace a key."""
    return load_host_bench_review_authority(workspace).for_observational_motion()


def load_host_absolute_wrist_review_authority(workspace):
    """Derive the absolute diagnostic domain from the existing protected key."""
    return load_host_bench_review_authority(workspace).for_absolute_wrist_diagnostic()


def load_host_wrist_correction_review_authority(workspace):
    """Derive correction authority from an existing protected key; never provision."""
    return load_host_bench_review_authority(workspace).for_wrist_correction_review()


def load_host_positional_campaign_review_authority(workspace):
    """Derive campaign authority from existing protected storage; never provision."""
    return load_host_bench_review_authority(workspace).for_positional_campaign()


def _crypt(raw, *, decrypt):
    """Noninteractive current-user DPAPI; native buffers cleared before freeing."""
    if os.name!='nt': raise RuntimeError('Windows current-user DPAPI required')
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BLOB:
        raise ValueError('Bounded DPAPI input required')
    crypt = C.WinDLL('crypt32',use_last_error=True)
    kernel = C.WinDLL('kernel32',use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [C.POINTER(_Blob),C.c_void_p,C.POINTER(_Blob),C.c_void_p,
                         C.c_void_p,W.DWORD,C.POINTER(_Blob)]
    function.restype = W.BOOL
    kernel.LocalFree.argtypes = [C.c_void_p]
    kernel.LocalFree.restype = C.c_void_p
    source = (C.c_ubyte*len(raw)).from_buffer_copy(raw)
    entropy = (C.c_ubyte*len(_ENTROPY)).from_buffer_copy(_ENTROPY)
    source_blob, entropy_blob = _Blob(len(raw),source),_Blob(len(_ENTROPY),entropy)
    output = _Blob()
    try:
        # UI_FORBIDDEN only: never LOCAL_MACHINE, reserved/prompt/description NULL.
        if not function(C.byref(source_blob),None,C.byref(entropy_blob),None,None,1,C.byref(output)):
            # LocalFree in finally can overwrite the thread's last-error slot.
            raise BenchKeyProtectionError(C.get_last_error())
        if not output.data or not 0 < output.size <= MAX_BLOB:
            raise RuntimeError('DPAPI output outside budget')
        return C.string_at(output.data,output.size)
    finally:
        C.memset(source,0,len(source))
        if output.data:
            C.memset(output.data,0,output.size)
            kernel.LocalFree(C.cast(output.data,C.c_void_p))


def _path(root):
    return contained_path(safe_root(Path(root)),FILENAME,label='private review key')


def provision_bench_review_key(root):
    """Explicit local setup only; an existing/partial key is never overwritten."""
    path = _path(root)
    if path.exists(): raise ValueError('Review key already exists; no automatic rotation')
    key = secrets.token_bytes(32)
    protected = _crypt(_DOMAIN+key,decrypt=False)
    if _crypt(protected,decrypt=True)!=_DOMAIN+key:
        raise RuntimeError('Protected review key roundtrip failed')
    publish_reservation_bytes(path.parent,path.name,protected,maximum_bytes=MAX_BLOB)
    if read_bounded_regular_file(path,maximum_bytes=MAX_BLOB)!=protected:
        raise RuntimeError('Protected review key publication mismatch')
    return {'authority_id':'local-bench-review-v1','status':'KEY_PROVISIONED',
            'protection':'WINDOWS_DPAPI_CURRENT_USER','physical_authority':False}


def load_bench_review_authority(root):
    """Load only; missing/corrupt/wrong-user storage never generates another key."""
    protected = read_bounded_regular_file(_path(root),maximum_bytes=MAX_BLOB)
    original = _crypt(protected,decrypt=True)
    if len(original)!=len(_DOMAIN)+32 or not original.startswith(_DOMAIN):
        raise ValueError('Protected review key domain or length mismatch')
    return BenchReviewAuthority(original[len(_DOMAIN):])

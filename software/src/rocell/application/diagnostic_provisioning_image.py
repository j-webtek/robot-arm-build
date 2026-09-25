"""Offline-only LittleFS staging; never opens a device or publishes secret bytes.

The caller supplies the pinned filesystem implementation and native policy
validator. Returned image bytes contain secrets and belong in private storage.
This module deliberately has no device-write or auto-format fallback.
"""
import hashlib


POLICY_PATH = '/rocell-diagnostics.json'
KEY_PATH = '/rocell-diagnostics.key'
STARTUP_POLICY_PATH = '/rocell-startup.json'
STARTUP_KEY_PATH = '/rocell-startup.key'
HOLD_POLICY_PATH = '/rocell-hold.json'
HOLD_KEY_PATH = '/rocell-hold.key'
IMAGE_SIZE = 352 * 4096


def stage_image(source, expected_sha256, policy, key, *, littlefs, validate_policy):
    return _stage_image(source, expected_sha256, policy, key, littlefs=littlefs,
        validate_policy=validate_policy, policy_path=POLICY_PATH, key_path=KEY_PATH,
        schema='rocell.offline_provisioning_image.v1')


def stage_startup_image(source, expected_sha256, policy, key, *, littlefs, validate_policy):
    """Distinct startup-only paths; caller must supply the bound startup validator.

    The validator must match the reviewed candidate, and that candidate must be
    installed/verified before any later provisioning. This function only stages
    bytes in memory; it neither generates a key nor approves persistent writes.
    """
    from .wizard_diagnostic_coordinator import decode_diagnostic_json
    if type(policy) is not bytes:raise ValueError('Startup policy bytes required')
    document=decode_diagnostic_json(policy,maximum=4096)
    if (type(document) is not dict or set(document)!={'schema','controller_policy','startup_policy'} or
            document['schema']!='rocell.controller_startup.v1'):
        raise ValueError('Explicit startup configuration required')
    return _stage_image(source, expected_sha256, policy, key, littlefs=littlefs,
        validate_policy=validate_policy, policy_path=STARTUP_POLICY_PATH, key_path=STARTUP_KEY_PATH,
        schema='rocell.offline_startup_provisioning_image.v1')


def stage_hold_image(source, expected_sha256, policy, key, *, littlefs, validate_policy):
    """Stage separate hold files; preserve startup files and every other entry.

    Caller supplies the installed r7 parser and key. This neither generates a
    credential nor authorizes writing the returned secret-bearing image.
    """
    from .wizard_diagnostic_coordinator import decode_diagnostic_json
    if type(policy) is not bytes or not 0 < len(policy) < 2048:
        raise ValueError('Bounded hold configuration bytes required')
    document = decode_diagnostic_json(policy, maximum=2047)
    if (type(document) is not dict or set(document) !=
            {'schema', 'command_id', 'hold_policy', 'start_port'} or
            document['schema'] != 'rocell.controller_hold.v1'):
        raise ValueError('Explicit hold configuration required')
    return _stage_image(source, expected_sha256, policy, key, littlefs=littlefs,
        validate_policy=validate_policy, policy_path=HOLD_POLICY_PATH, key_path=HOLD_KEY_PATH,
        schema='rocell.offline_hold_provisioning_image.v1')


def _stage_image(source, expected_sha256, policy, key, *, littlefs, validate_policy,
                 policy_path, key_path, schema, previous_policy=None,
                 preserve_key=False, required_existing=None):
    """Return a verified in-memory candidate and a nonsecret review summary.

Policy acceptance must come from the installed firmware's parser, not a test
fixture or permissive JSON check. Acceptance does not establish physical safety.
No output is returned unless remount and every existing-file comparison succeed.
"""
    if (type(source) is not bytes or len(source) != IMAGE_SIZE or
            hashlib.sha256(source).hexdigest() != expected_sha256):
        raise ValueError('Source image identity mismatch')
    if type(policy) is not bytes or not 0 < len(policy) <= 4096:
        raise ValueError('Invalid policy size')
    replacing = previous_policy is not None
    if not replacing and not preserve_key and (type(key) is not bytes or len(key) != 32 or
            key == bytes(32) or key == bytes(range(32))):
        raise ValueError('Invalid diagnostic key')
    if littlefs.__version__ != '0.19.0':
        raise ValueError('Unreviewed filesystem implementation')
    if validate_policy(policy) is not True:
        raise ValueError('Native policy validation failed')

    def mount(data):
        context = littlefs.UserContext(buffer=bytearray(data))
        fs = littlefs.LittleFS(context=context, mount=False, block_size=4096,
                              block_count=352, read_size=256, prog_size=256)
        fs.mount()  # Explicit mount: never constructor auto-format on failure.
        return fs, context

    def inventory(fs, path='/'):
        result = {}
        for entry in fs.scandir(path):
            child = path.rstrip('/') + '/' + entry.name
            if entry.type == 2:
                result[child] = ('directory',)
                result.update(inventory(fs, child))
            elif entry.type == 1:
                with fs.open(child, 'rb') as stream:
                    data = stream.read()
                result[child] = ('file', len(data), hashlib.sha256(data).hexdigest())
            else:
                raise ValueError('Unsupported filesystem entry')
        return result

    fs, context = mount(source)
    try:
        before = inventory(fs)
        for path, expected in (required_existing or {}).items():
            if path not in before:raise ValueError('Required existing configuration missing')
            with fs.open(path, 'rb') as stream:
                if stream.read()!=expected:raise ValueError('Existing configuration differs')
        if replacing:
            if policy_path not in before or key_path not in before:
                raise ValueError('Existing hold configuration and key required')
            with fs.open(policy_path, 'rb') as stream:
                if stream.read() != previous_policy:
                    raise ValueError('Previous policy identity mismatch')
            with fs.open(key_path, 'rb') as stream:
                key = stream.read(33)
            if len(key) != 32 or key in (bytes(32), bytes(range(32))):
                raise ValueError('Invalid retained key')
        elif preserve_key:
            if key is not None or policy_path in before or key_path not in before:
                raise ValueError('New settings and an existing key required')
            with fs.open(key_path, 'rb') as stream:key=stream.read(33)
            if len(key)!=32 or key in (bytes(32),bytes(range(32))):
                raise ValueError('Invalid retained key')
        elif policy_path in before or key_path in before:
            raise ValueError('Provisioning destinations already exist')
        writes = ((policy_path, policy),) if replacing or preserve_key else ((policy_path, policy), (key_path, key))
        for path, data in writes:
            with fs.open(path, 'wb' if replacing else 'xb') as stream:
                if stream.write(data) != len(data):
                    raise ValueError('Incomplete offline write')
    finally:
        fs.unmount()
    candidate = bytes(context.buffer)
    fs, _ = mount(candidate)
    try:
        after = inventory(fs)
        if set(after) != set(before) | {policy_path, key_path}:
            raise ValueError('Unexpected filesystem inventory change')
        if any(after[path] != value for path, value in before.items()
               if not (replacing and path == policy_path)):
            raise ValueError('Existing filesystem content changed')
        for path, expected in ((policy_path, policy), (key_path, key)):
            with fs.open(path, 'rb') as stream:
                if stream.read() != expected:
                    raise ValueError('Provisioned readback mismatch')
    finally:
        fs.unmount()
    return candidate, {
        'schema': schema,
        'source_sha256': expected_sha256,
        'candidate_sha256': hashlib.sha256(candidate).hexdigest(),
        'policy_sha256': hashlib.sha256(policy).hexdigest(),
        'existing_entries_preserved': len(before) - int(replacing),
        'remount_verified': True, 'device_modified': False,
        'physical_authority': 'NONE',
    }


def stage_pair_settings_image(source, expected_sha256, settings, expected_hold_policy,
                              *, littlefs, validate_settings, validate_hold_policy):
    """Add only /rocell-pair.json; retain hold policy, key and every other file.

    Validators must be the reviewed native parsers. The returned image contains
    credentials: keep it private. This function neither saves nor deploys it.
    """
    from .held_pair_settings import decode_pair_settings
    decode_pair_settings(settings)
    if (type(expected_hold_policy) is not bytes or not 0<len(expected_hold_policy)<2048
            or validate_hold_policy(expected_hold_policy) is not True):
        raise ValueError('Reviewed existing hold policy required')
    candidate, review = _stage_image(source,expected_sha256,settings,None,littlefs=littlefs,
        validate_policy=validate_settings,policy_path='/rocell-pair.json',key_path=HOLD_KEY_PATH,
        schema='rocell.offline_pair_settings_image.v1',preserve_key=True,
        required_existing={HOLD_POLICY_PATH:expected_hold_policy})
    review.update(settings_sha256=review.pop('policy_sha256'),
        hold_policy_sha256=hashlib.sha256(expected_hold_policy).hexdigest(),
        existing_key_preserved=True,key_generated=False,provisioning_performed=False)
    return candidate,review


def replace_pair_direction_image(source, expected_sha256, previous_settings, settings,
                                 expected_hold_policy, *, littlefs,
                                 validate_settings, validate_hold_policy):
    """Offline direction-only replacement; exact prior bytes and image required.

    Does not deploy or persist the secret-bearing result. Callers need separate
    approval for private staging and controller provisioning. All other settings,
    hold policy, credentials and files are preserved by the shared image checker.
    """
    from .held_pair_settings import decode_pair_settings
    previous = decode_pair_settings(previous_settings)
    proposed = decode_pair_settings(settings)
    if (previous['offset_counts'] != 6 or proposed['offset_counts'] != -6 or
            any(previous[k] != proposed[k] for k in previous if k != 'offset_counts')):
        raise ValueError('Only the reviewed +6 to -6 direction change is supported')
    if validate_settings(previous_settings) is not True or validate_settings(settings) is not True:
        raise ValueError('Native pair settings validation failed')
    if (type(expected_hold_policy) is not bytes or not 0 < len(expected_hold_policy) < 2048
            or validate_hold_policy(expected_hold_policy) is not True):
        raise ValueError('Reviewed unchanged hold policy required')
    candidate, report = _stage_image(source, expected_sha256, settings, None,
        littlefs=littlefs, validate_policy=validate_settings,
        policy_path='/rocell-pair.json', key_path=HOLD_KEY_PATH,
        previous_policy=previous_settings,
        required_existing={HOLD_POLICY_PATH: expected_hold_policy},
        schema='rocell.offline_pair_direction_replacement.v1')
    report.update(settings_sha256=report.pop('policy_sha256'),
        hold_policy_sha256=hashlib.sha256(expected_hold_policy).hexdigest(),
        existing_key_preserved=True, key_generated=False, provisioning_performed=False)
    return candidate, report


def replace_hold_policy_image(source, expected_sha256, previous_policy, policy, *,
                              littlefs, validate_policy):
    """Explicit offline replacement; preserve the existing key and other files.

    Exact prior bytes are mandatory. Never generates a credential, formats a
    filesystem, opens a controller, or publishes the secret-bearing image.
    """
    from .wizard_diagnostic_coordinator import decode_diagnostic_json
    for value in (previous_policy, policy):
        if type(value) is not bytes or not 0 < len(value) < 2048:
            raise ValueError('Bounded hold configuration required')
        document = decode_diagnostic_json(value, maximum=2047)
        if (type(document) is not dict or set(document) !=
                {'schema', 'command_id', 'hold_policy', 'start_port'} or
                document['schema'] != 'rocell.controller_hold.v1' or
                validate_policy(value) is not True):
            raise ValueError('Native hold configuration validation failed')
    if policy == previous_policy:
        raise ValueError('Replacement policy must differ')
    return _stage_image(source, expected_sha256, policy, None, littlefs=littlefs,
        validate_policy=validate_policy, policy_path=HOLD_POLICY_PATH,
        key_path=HOLD_KEY_PATH, previous_policy=previous_policy,
        schema='rocell.offline_hold_policy_replacement.v1')


def replace_observed_pose_image(source, expected_sha256, previous_hold, previous_pair,
                                hold, pair, *, littlefs, validate_hold, validate_pair):
    """Compose the reviewed two-file replacement entirely in memory.

    No intermediate image is returned or persisted. Each remount proves all
    unrelated entries unchanged, including the diagnostic key and credentials.
    Actual private staging and installation require separate user authorization.
    Native validators must come from the reviewed installed firmware parsers.
    """
    expected = (
        '2ab588877107ebbc067607c29003fb317867123780e40c8e9d41011907d312d1',
        '471898fe914f0843bdd88556b98aa1277c29d672c628df5892bd5bd849a8f314',
        'cb844a0818b501f9186cf4e421628d28ea4c3e8c583e2171d6d15f62a0dc4354',
        '0dade56675bc9767358888d78c34258121f65e3eae7f92b95ed5b77cfc5b2835')
    documents = (previous_hold, previous_pair, hold, pair)
    if any(type(raw) is not bytes for raw in documents) or tuple(
            hashlib.sha256(raw).hexdigest() for raw in documents) != expected:
        raise ValueError('Exact reviewed observed-pose replacement required')
    if any(check(raw) is not True for check, raw in (
            (validate_hold, previous_hold), (validate_hold, hold),
            (validate_pair, previous_pair), (validate_pair, pair))):
        raise ValueError('Native configuration validation failed')
    intermediate, first = _stage_image(source, expected_sha256, hold, None,
        littlefs=littlefs, validate_policy=validate_hold, policy_path=HOLD_POLICY_PATH,
        key_path=HOLD_KEY_PATH, previous_policy=previous_hold,
        required_existing={'/rocell-pair.json': previous_pair},
        schema='rocell.offline_observed_hold_step.v1')
    candidate, second = _stage_image(intermediate, first['candidate_sha256'], pair, None,
        littlefs=littlefs, validate_policy=validate_pair, policy_path='/rocell-pair.json',
        key_path=HOLD_KEY_PATH, previous_policy=previous_pair,
        required_existing={HOLD_POLICY_PATH: hold},
        schema='rocell.offline_observed_pair_step.v1')
    return candidate, dict(schema='rocell.offline_observed_pose_replacement.v1',
        source_sha256=expected_sha256, candidate_sha256=second['candidate_sha256'],
        previous_hold_sha256=expected[0], previous_pair_sha256=expected[1],
        hold_sha256=expected[2], pair_sha256=expected[3],
        changed_paths=[HOLD_POLICY_PATH, '/rocell-pair.json'],
        existing_entries_preserved=first['existing_entries_preserved']-1,
        unrelated_entries_preserved=True, existing_key_preserved=True,
        remount_verified=True, device_modified=False, provisioning_performed=False,
        physical_authority='NONE')

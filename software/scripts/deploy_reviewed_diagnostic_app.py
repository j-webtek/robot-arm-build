"""One authorized app-only deployment; fixed image/offset, no provisioning/motion."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

APP_HASH = '5d1e081a1b33ddf9eb85a248112c6d18484e04417a1b87042f805875414ba481'
R3_HASH = '46e23efb7f9f18557882b1b185ecf4874ba4b2123ef64867f3a2831c56e01ee1'
R6_HASH = '71447b72f1488954ece0f6e9d95ca6ec3fc14b45982a10d65a96d3caa3691526'
R7_HASH = '380d7a69e0b456b25b4ae50e34f8d947724ca5c22db42d75958df509e2618c33'
R10_HASH = 'b07fd9a442bfeb58a9b846828a5b6cedf25441fd9ce322be9f8f72f32ef9389d'
R11_HASH = '52979050aa4fabbe167f01fc1bb7b656105cb370d54f3dd9890c5f6703682b52'
R12_HASH = '81227435b8d6b3e36da8e43cd06e88b7d5872e6fc6566eb8d0a5b9a69d7da41d'
R13_HASH = '4503aaa00409624ebc0a54876c45eec5af684a6717327046d34a5e7c644b9a6e'
R14_HASH = '83ad71a221168ae59c65fc711f781ba6532a996b9b9d28464647ca19e0441281'
R16_HASH = 'dc8b6f0016d29495ef6403d6a04adcbc192ec45ccd1ede7c390c3d1b4b3ea05e'
R17_HASH = '0ed01a2294b19047d95aeeeaf48af6c12d5610128cebe0bd94ca4119ccd5715b'
R19_HASH = '18d5586456f4d3552b88edcd3770c6c97677aacfce66eb6dcc33cd2b2914f8ce'
R20_HASH = '188e7a96ef11e516655f2f8b9e3efeecb4947a501bdc1ae2beda5cffb5da9572'
R21_HASH = '035922452587280362fc1e6fe0120f274647eeb2b0f8ee3c7bc88cb8c3289051'
R22_HASH = '047beb3ac792a2c5f85c2b10138d0ca9bd47ae80359af7312138e56f0d132679'
R23_HASH = '9edf6bbcf1052a8191d7ecac37195867bb8fafd0149bcaecf585834c807f579b'
R24_HASH = 'fe3eaec72bb31f72210bec45912b8d5bb4df27adcb292a94decf15106a9436be'
R25_HASH = '483604c16de0b2061335873fdc176b90551e16e7552fcd2aa6058e6449bbde5f'
R26_HASH = '2a17bdf5a24cb1a3032d0212ca3c2db11d1f6a5b2027fdaf45b44f9c5e4f3c78'
R27_HASH = 'c46e1ab78cb6b38c1244f1da8dd8b459340704b65af093c3b1875ed3d6158bba'
R28_HASH = '88ccd20ebb1607a130cc25f6c5026690cd258cb14ba0d1b0bd763f32540f232e'
R29_HASH = 'd9d61fc6bcc3b32b6e84a6d3065dcd6bbbf96d374243b83fb140c9e5395baa00'
R31_HASH = 'e8400d1c302a70bed3283c4102fa6b202785c1ea35826de2e98754a09b80fae3'
R33_HASH = '170188fe380cc7a21ee5502e831f21c3050b34768bdbbbbc1ddf7f7e608b330d'
R34_HASH = '6637e0e6f06b731db23621d8a727cdc0f9b82a2473813eec9a3b8a98fbd09945'
R35_HASH = 'c34ebe285db2e31be5c0f4ed35497cd13c280c82a130ac690e120c23f94cda91'
R36_HASH = '1e8564d204aa773149ad54fc58fd70bee294bdfdea74e8d29b2f07de19417dfd'
R37_HASH = '24a3f58df32b5c3db77a6952ed22bf1eddc79c535760afc90abcc67d8e8806ee'
R38_HASH = 'eee1b0f9b8b835573e0237f830108e2f4ead3f88efc3a11651401c7130f0d92e'
R39_HASH = '590a2f942214e9830fdfda9ad9610cf4c71c9fec818aa3dacabc02a6291f1156'
R40_HASH = '0bdfad949388b758fff3b8b177a24c9da87e7089ed6a952c6a03b6daf9833213'
R41_HASH = 'caa26535377b8f35e3bfdc8d0546c779db052a520a355eaab455dcf64defc5cf'
R42_HASH = '6d3405b3b42db9347ec02445b0937886ca0fba82bf38d905e3989ad48c8f71ea'
R43_HASH = '459e1f31ac103c634b2205654501693d9116bded2bcd9ac1bf8de5284a20fb1b'
R44_HASH = 'f1910697b4653c941974e9dc9939357ccfe7a7016c526285465decdea2614d7d'
R45_HASH = '3b9e5930b9818ee4c4425541f6100d8dc22320eadd883f9d4391ff8499487af6'
R46_HASH = '1b205cffb023761f228be728a8caee9de0e13b17751d4bec28b6ba5584c83d87'
R47_HASH = 'a2101ea8ec27b7f9c93063b3e5dea91546b91b2edfbca63b3cc5e71f3f7cee1e'
R48_HASH = 'e76470e40216c39dd6ebc57df3e665c50fa6436da680bbeea0b18c599deddc1b'
R49_HASH = 'e4b331623527aa94078e514f8cd37e18ac00a04bf543b9005072ff677a42c21f'
R50_HASH = '0dda0988222a1de534a5d72de1f528f6ae42fed5be0215fed8fbd75129e6121b'
R51_HASH = '0a45c55ace66374038c712672bee41b507a80e64a121b0a020b4836ce2bddc9e'
R52_HASH = '0389e22b97cb9e87a97dc4491746af385d3dfcf76c00daaaab434a36b088738b'
R53_HASH = '8d5ed3f0feb491e2294bb6f56bf27f82c53f616d257c61f493df58d94f050de5'
R54_HASH = 'c418af3062200c91e6cdf4c5540a7e251f09cdc36fccb9659a9b9a6181f818fe'
R55_HASH = '1ea884af0cd717775c67046302ab5e9df82b9514b552b96fc8d27d5ad853d9a5'
R56_HASH = '09864d144d630b2655c78956b0ea8148b0525bcdef017caa843d74f1f4661e79'
R57_HASH = '7d8ac14ae59272368fbf3031ebc3ad5a5835e84913d85ee5758df46670767b68'
R58_HASH = '944155ce47d2eeb60e6c7e7cb12d687a9250c6b3c030de49d39c9e923dc544f5'
R60_HASH = '6f98f372b5a927b016ae81f0673df1ee8ddd0f0b78bc714d181746e575df7211'
R61_HASH = '5f713ae53577b3a4dc6a6419f2a3b84563b2db89f903be9c24bc496482f41451'
R62_HASH = 'ee259799cb6b74b80cc4a45e16934ac6476b81d7a4536cc31406fffb766fd6e4'
R63_HASH = 'cbca0f164c49f480c282fe2ed435616a50a767db50b1048b24b7abb40e55604b'
SUPPORTED_FS_HASH = '4524696545583513b283348789b2e1f92ed37e178efcb10edf32dcbd639ec4bf'
R6_FS_HASH = '567d3cc0f20b2a5843bf27c7aac069f0df18782234f8579fae48a73604e569c6'
R6_FS_SOURCE = 'd219fd8b7e3946550acc7153671765a8fc327613dfdcc2952957b13bb331b022'
R6_PROVISIONING_EXPORT = 'wizard-20260918T162143375438Z-d90ecc6ffbc74a6da9bcb8ad6fac1f24'
BACKUP_HASH = 'd9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9'
RECOVERY_HASH = '50dbba429355156d0bbd77e603a777ed2d2a289a21a00f6df042ae6fc5bfbf6b'


def checked(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Approved artifact hash mismatch')
    return data


def revision_spec(revision):
    """Explicit reviewed upgrade edges; no arbitrary image or revision fallback."""
    specs = {
        2: (APP_HASH, 1072832, None, 'app-deployment-events.jsonl'),
        3: (R3_HASH, 1076384, 2, 'app-r3-deployment-events.jsonl'),
        6: (R6_HASH, 1081872, 3, 'app-r6-deployment-events.jsonl'),
        7: (R7_HASH, 1070912, 6, 'app-r7-deployment-events.jsonl'),
        10: (R10_HASH, 1103808, 7, 'app-r10-deployment-events.jsonl'),
        11: (R11_HASH, 1103872, 10, 'app-r11-deployment-events.jsonl'),
        12: (R12_HASH, 1103920, 11, 'app-r12-deployment-events.jsonl'),
        13: (R13_HASH, 1104048, 12, 'app-r13-deployment-events.jsonl'),
        14: (R14_HASH, 1106528, 13, 'app-r14-deployment-events.jsonl'),
        16: (R16_HASH, 1120240, 14, 'app-r16-deployment-events.jsonl'),
        17: (R17_HASH, 1122416, 16, 'app-r17-deployment-events.jsonl'),
        19: (R19_HASH, 1122896, 17, 'app-r19-deployment-events.jsonl'),
        20: (R20_HASH, 1127072, 19, 'app-r20-deployment-events.jsonl'),
        21: (R21_HASH, 1127424, 20, 'app-r21-deployment-events.jsonl'),
        22: (R22_HASH, 1129648, 21, 'app-r22-deployment-events.jsonl'),
        23: (R23_HASH, 1141360, 22, 'app-r23-deployment-events.jsonl'),
        24: (R24_HASH, 1141424, 23, 'app-r24-deployment-events.jsonl'),
        25: (R25_HASH, 1142688, 24, 'app-r25-deployment-events.jsonl'),
        26: (R26_HASH, 1143376, 25, 'app-r26-deployment-events.jsonl'),
        27: (R27_HASH, 1145280, 26, 'app-r27-deployment-events.jsonl'),
        28: (R28_HASH, 1145728, 27, 'app-r28-deployment-events.jsonl'),
        29: (R29_HASH, 1146336, 28, 'app-r29-deployment-events.jsonl'),
        # r30 was reviewed offline only; the device predecessor remains r29.
        31: (R31_HASH, 1150592, 29, 'app-r31-deployment-events.jsonl'),
        33: (R33_HASH, 1154048, 31, 'app-r33-deployment-events.jsonl'),
        36: (R36_HASH, 1155600, 35, 'app-r36-deployment-events.jsonl'),
        37: (R37_HASH, 1156080, 36, 'app-r37-deployment-events.jsonl'),
        38: (R38_HASH, 1156048, 37, 'app-r38-deployment-events.jsonl'),
        39: (R39_HASH, 1156384, 38, 'app-r39-deployment-events.jsonl'),
        40: (R40_HASH, 1156384, 39, 'app-r40-deployment-events.jsonl'),
        41: (R41_HASH, 1156992, 40, 'app-r41-deployment-events.jsonl'),
        42: (R42_HASH, 1156992, 41, 'app-r42-deployment-events.jsonl'),
        43: (R43_HASH, 1156992, 42, 'app-r43-deployment-events.jsonl'),
        44: (R44_HASH, 1157616, 43, 'app-r44-deployment-events.jsonl'),
        45: (R45_HASH, 1157616, 44, 'app-r45-deployment-events.jsonl'),
        46: (R46_HASH, 1157936, 45, 'app-r46-deployment-events.jsonl'),
        47: (R47_HASH, 1157936, 46, 'app-r47-deployment-events.jsonl'),
        48: (R48_HASH, 1158256, 47, 'app-r48-deployment-events.jsonl'),
        49: (R49_HASH, 1158528, 48, 'app-r49-deployment-events.jsonl'),
        50: (R50_HASH, 1158736, 49, 'app-r50-deployment-events.jsonl'),
        51: (R51_HASH, 1158992, 50, 'app-r51-deployment-events.jsonl'),
        52: (R52_HASH, 1159328, 51, 'app-r52-deployment-events.jsonl'),
        53: (R53_HASH, 1159392, 52, 'app-r53-deployment-events.jsonl'),
        54: (R54_HASH, 1167056, 53, 'app-r54-deployment-events.jsonl'),
        55: (R55_HASH, 1175216, 54, 'app-r55-deployment-events.jsonl'),
        56: (R56_HASH, 1175728, 55, 'app-r56-deployment-events.jsonl'),
        57: (R57_HASH, 1183296, 56, 'app-r57-deployment-events.jsonl'),
        58: (R58_HASH, 1183232, 57, 'app-r58-deployment-events.jsonl'),
        # r59 failed offline compilation and was never installed.
        60: (R60_HASH, 1183360, 58, 'app-r60-deployment-events.jsonl'),
        61: (R61_HASH, 1183616, 60, 'app-r61-deployment-events.jsonl'),
        62: (R62_HASH, 1192368, 61, 'app-r62-deployment-events.jsonl'),
        63: (R63_HASH, 1200704, 62, 'app-r63-deployment-events.jsonl'),
        64: ('a8480d215bdfce5768dd0fcd6d81c97bab9cae9c6b2d33ea0894eefe28275ba8', 1200720, 63, 'app-r64-deployment-events.jsonl'),
        65: ('7ed18ca356194e2b226936c5146e46ec079c326d8140667a07a49923b935b4de', 1200624, 64, 'app-r65-deployment-events.jsonl'),
        66: ('3dd1401b58cec43fb3c5c27c8d2072987487964d8a4609552d38cf8bf7e73812', 1200656, 65, 'app-r66-deployment-events.jsonl'),
        67: ('92623957b1a2bf9f11bafce8a3a8db6788121232d26cb6fed1406c0ecb002c05', 1200640, 66, 'app-r67-deployment-events.jsonl'),
        68: ('70ea81de94d578360a6afb68462b1e87b660b0c7a4bf1d5c644491ba7136dbad', 1200720, 67, 'app-r68-deployment-events.jsonl'),
        69: ('121a4c5b98c7fbb6e94ad448ac056341c284530416bf583c690850792b12a7a8', 1200640, 68, 'app-r69-deployment-events.jsonl'),
        70: ('d4e860492602492477e67e58436a681a252adc2b9eeb934315abb05b98113134', 1200656, 69, 'app-r70-deployment-events.jsonl'),
        72: ('e8d27dc8085d4e21ae6450be4eff0c41eb46a39962ba2d47baf084b01ee3afe9', 1202960, 71, 'app-r72-deployment-events.jsonl'),
        73: ('ec2b9f63e6c2157185584f596a7a04551c995bed9de811d9bcd94b7bc3c2373a', 1203040, 72, 'app-r73-deployment-events.jsonl'),
        74: ('1f2c6822f428b9dd9fdf2eb17444d3f89f5d7243a7aad89edae4acda0b721bc5', 1203024, 73, 'app-r74-deployment-events.jsonl'),
        75: ('da56d6d353918f2654f919914a48a8de4f3a7377ee718c5c122dac397bb92f2d', 1203040, 74, 'app-r75-deployment-events.jsonl'),
        76: ('874c89ca5af7bbb5e492cb5b3cf95ea47116c19fc65190151c638e47aeac0987', 1202960, 75, 'app-r76-deployment-events.jsonl'),
        77: ('7a2059d76243b37e9b443c822093ef597611f136f5497a055f01278c3bcda496', 1203152, 76, 'app-r77-deployment-events.jsonl'),
        78: ('3b9989e03cd64690e831049c4e19ff38d6c10ab6e2c6c22f3ad1d7e61e1f3aaa', 1204848, 77, 'app-r78-deployment-events.jsonl'),
        79: ('f82f1f87e6e9917dfdf2e9c60c30aaedf18025bdbd3b9777600b46a1458f7e82', 1204896, 78, 'app-r79-deployment-events.jsonl'),
        81: ('2580a872ce612c331cb02dce15be9b34f75f1e19ac4bc6043072e438e8b948d1', 1204944, 79, 'app-r81-deployment-events.jsonl'),
        82: ('0be3db4edf21396c881ee9eeee62f625bc99ebaf33bf96b35656c5dffd3a937c', 1204912, 81, 'app-r82-deployment-events.jsonl'),
        83: ('5baaa670dd27e1e1f621fa5357f67eba765101b182be4513908e30192d4a00d6', 1205024, 82, 'app-r83-deployment-events.jsonl'),
        84: ('d1e141a9b73d0b104ffb2ac1b07cae213c1321300a2251bd8cd3dcf0596f97cd', 1204880, 83, 'app-r84-deployment-events.jsonl'),
        71: ('1ebaff62ea6348f072c35ce48005f67f5e2ff025c1c43de046ff23086bdcbf0b', 1200640, 70, 'app-r71-deployment-events.jsonl'),
        35: (R35_HASH, 1155456, 34, 'app-r35-deployment-events.jsonl'),
        34: (R34_HASH, 1155184, 33, 'app-r34-deployment-events.jsonl'),
    }
    if type(revision) is not int or revision not in specs:
        raise ValueError('Unreviewed application revision')
    return specs[revision]


def provisioned_filesystem(root, private):
    """Verify saved provisioning evidence before decrypting the private image.

    Never mount it, extract its key, write plaintext, or export its contents.
    This establishes expected bytes, not the current device's filesystem.
    """
    from rocell.application.product_ghost_export_review import _read
    from rocell.providers.windows.diagnostic_image_store import load_image
    report, _ = _read(root / 'runs/wizard-exports', R6_PROVISIONING_EXPORT,
                      'attachment-provisioning-result.json')
    expected = dict(schema='rocell.startup_provisioning_result.v1',
        candidate_sha256=R6_FS_HASH, source_sha256=R6_FS_SOURCE,
        plan_export_id='wizard-20260918T160845323205Z-10ea70dd642141d7bb0c1b931c45b865',
        configuration_loaded=False, motion_authorized=False,
        protected_regions_unchanged=True, recovery_preserved=True, retry_allowed=False,
        startup_attempted=False, status='FLASH_READBACK_VERIFIED')
    if report != expected:
        raise ValueError('Reviewed provisioning result differs')
    image = load_image(private / 'startup-r6-candidate.dpapi')
    if len(image) != 0x160000 or hashlib.sha256(image).hexdigest() != R6_FS_HASH:
        raise ValueError('Reviewed provisioned filesystem differs')
    return image


def supported_pose_filesystem(root, private):
    """Bind the latest verified replacement, not the older r6 or factory image.

    Saved receipts establish expected bytes only. Device MD5 checks still run
    before any authorized write. Plaintext stays in memory and is never mounted.
    """
    from rocell.application.product_ghost_export_review import _read
    from rocell.providers.windows.diagnostic_image_store import load_image
    exports = root / 'runs/wizard-exports'
    write_id = 'wizard-20260918T213520661096Z-ba47bd4a42bf42a2ba60007158b265e1'
    run_id = 'wizard-20260918T213520824547Z-50d496655d5d4796b58d39a0a8395a1a'
    expected = dict(schema='rocell.hold_provisioning_result.v1',
        candidate_sha256=SUPPORTED_FS_HASH,
        source_sha256='0bdfc4d3f300e811e03332a6a86df20e47c3d42c95282e9ddd2f00c211044e9b',
        plan_export_id='wizard-20260918T212222293772Z-63b5b72a4b0a4cf19da8721aeed006fc',
        configuration_loaded=False, motion_authorized=False,
        protected_regions_unchanged=True, recovery_preserved=True, retry_allowed=False,
        startup_attempted=False, status='FLASH_READBACK_VERIFIED')
    write, _ = _read(exports, write_id, 'attachment-provisioning-result.json')
    run, _ = _read(exports, run_id, 'attachment-provisioning-run.json')
    if write != expected or run != dict(expected, startup_attempted=True,
            application_health_verified=False, verified_write_export_id=write_id):
        raise ValueError('Supported-pose provisioning receipt differs')
    image = load_image(private / 'hold-r7-supported-replacement-candidate.dpapi')
    if len(image) != 0x160000 or hashlib.sha256(image).hexdigest() != SUPPORTED_FS_HASH:
        raise ValueError('Supported-pose filesystem differs')
    return image


def pair_settings_filesystem(root, private):
    """Retain the verified pair settings and credentials, never the older image."""
    from rocell.application.r10_provisioned_evidence import review_provisioned_r10, CANDIDATE
    from rocell.providers.windows.diagnostic_image_store import load_image
    review_provisioned_r10(root)
    image = load_image(private / 'pair-r10-settings-candidate.dpapi')
    if len(image) != 0x160000 or hashlib.sha256(image).hexdigest() != CANDIDATE:
        raise ValueError('Pair-settings filesystem differs')
    return image


def second_r27_journal(root, revision):
    """Explicit second attempt after one pinned prewrite failure, never a resume."""
    if type(revision) is not int or revision != 27:
        raise ValueError('Second-attempt authorization is r27 only')
    private = root / 'private-backups/controller-20260918-session1'
    checked(private / 'app-r27-deployment-events.jsonl',
            'cd7f3ff5750b08af350afbf7e41f2e92c828f2e991181ef48578050591242042')
    from rocell.application.held_pair_installation_evidence import review_pair_installation
    from rocell.application.product_ghost_export_review import _read
    review_pair_installation(root, revision=26)
    recovery, _ = _read(root / 'runs/wizard-exports',
        'wizard-20260919T202608563404Z-c111bf72f6eb4528bf6d14e54536d326',
        'attachment-recovery-startup.json')
    if (recovery['status'] != 'ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED'
            or recovery['flash_written'] is not False
            or recovery['servo_command_sent'] is not False
            or recovery['settings_written'] is not False
            or recovery['failed_journal_sha256'] != 'cd7f3ff5750b08af350afbf7e41f2e92c828f2e991181ef48578050591242042'):
        raise ValueError('Pinned recovery evidence differs')
    return 'app-r27-attempt2-deployment-events.jsonl'


def second_r42_journal(root, revision):
    """One separate attempt after the exact r42 prewrite-only loader failure."""
    if type(revision) is not int or revision != 42:
        raise ValueError('Second r42 attempt authorization is r42 only')
    private = root / 'private-backups/controller-20260918-session1'
    failed_hash = '30abc7feff8027500a38c712b3e239be59cb81ae438ca6139495737dd3bde8ea'
    checked(private / 'app-r42-deployment-events.jsonl', failed_hash)
    from rocell.application.held_pair_installation_evidence import review_pair_installation
    from rocell.application.product_ghost_export_review import _read
    review_pair_installation(root, revision=41)
    recovery, _ = _read(root / 'runs/wizard-exports',
        'wizard-20260920T193603078018Z-f8da68cf462b432daba97f39da803971',
        'attachment-recovery-startup.json')
    if (recovery.get('schema') != 'rocell.r42_prewrite_recovery_r41_startup.v1'
            or recovery.get('status') != 'ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED'
            or recovery.get('failed_journal_sha256') != failed_hash
            or any(recovery.get(field) is not False for field in
                   ('servo_command_sent','flash_written','settings_written','retry_allowed'))):
        raise ValueError('Pinned r42 recovery evidence differs')
    return 'app-r42-attempt2-deployment-events.jsonl'


def second_r64_journal(root, revision):
    """Separate authorized attempt, bound to the exact retained prewrite failure."""
    if type(revision) is not int or revision != 64:
        raise ValueError('Second r64 attempt authorization is r64 only')
    private = root/'private-backups/controller-20260918-session1'
    failed_hash = '29e319d41ea6570da7063299c6cd7ac035494163ac4ac7521eb8f8497b6e3b40'
    checked(private/'app-r64-deployment-events.jsonl', failed_hash)
    from rocell.application.product_ghost_export_review import _read
    report, _ = _read(root/'runs/wizard-exports',
        'wizard-20260923T192629532955Z-a247925f78d749dd95c7a96845762233',
        'attachment-r64-prewrite-failure.json')
    if (report.get('journal_sha256') != failed_hash or
            report.get('status') != 'DOWNLOAD_MODE_DETECTED_NO_SYNC' or
            any(report.get(k) is not False for k in
                ('app_write_attempted', 'startup_reset_sent', 'movement_command_sent', 'retry_attempted'))):
        raise ValueError('Pinned r64 prewrite failure differs')
    return 'app-r64-attempt2-deployment-events.jsonl'


def second_r69_journal(root, revision):
    """Separate approved retry, bound to the preserved prewrite failure."""
    if type(revision) is not int or revision != 69:
        raise ValueError('Second r69 attempt authorization is r69 only')
    failed_hash = 'e39376fe1ca62161a027fcb31fcaa0338501c3e55ffbda8d5f8b99e6a2af80c1'
    checked(root/'private-backups/controller-20260918-session1/app-r69-deployment-events.jsonl', failed_hash)
    from rocell.application.product_ghost_export_review import _read
    report, _ = _read(root/'runs/wizard-exports',
        'wizard-20260924T095613508466Z-57acb13dbf8a46da868933267443ac23',
        'attachment-r69-prewrite-failure.json')
    if (report.get('journal_sha256') != failed_hash or
            report.get('status') != 'DOWNLOAD_MODE_DETECTED_NO_SYNC' or
            any(report.get(k) is not False for k in
                ('app_write_attempted', 'startup_reset_sent', 'movement_command_sent', 'retry_attempted'))):
        raise ValueError('Pinned r69 prewrite failure differs')
    return 'app-r69-attempt2-deployment-events.jsonl'


def longer_reset_rom(esptool, port):
    """Use the vendor's second Windows timing, with only one reset attempt."""
    from esptool.reset import ClassicReset, DEFAULT_RESET_DELAY
    class LongerResetROM(esptool.ESP32ROM):
        def _construct_reset_strategy_sequence(self, mode):
            if mode != 'default_reset':
                raise ValueError('Only reviewed default-reset mode permitted')
            return (ClassicReset(self._port, DEFAULT_RESET_DELAY + 0.5),)
    return LongerResetROM(port, baud=115200)


def preflight(root, revision, *, second_attempt=False):
    """Local reads only: no serial import/open, journal reservation or startup."""
    expected_hash, length, predecessor, journal_name = revision_spec(revision)
    if second_attempt:
        journal_name = (second_r27_journal(root, revision) if revision == 27
                        else second_r69_journal(root, revision) if revision == 69
                        else second_r64_journal(root, revision) if revision == 64
                        else second_r42_journal(root, revision))
    private = root / 'private-backups/controller-20260918-session1'
    def app_path(number):
        return root / f'.firmware-tools/build-configured-diagnostic-candidate-r{number}--default-4mb-no-psram/RoArm-M3_example.ino.bin'
    app = app_path(revision)
    image = checked(app, expected_hash)
    backup = checked(private / 'flash-pair-a.bin', BACKUP_HASH)
    checked(private / 'flash-pair-b.bin', BACKUP_HASH)
    recovery = checked(private / 'original-app0-slot.bin', RECOVERY_HASH)
    if len(image) != length or len(backup) != 4194304 or len(recovery) != 1310720:
        raise ValueError('Unexpected artifact sizes')
    previous = recovery
    if predecessor is not None:
        previous_hash, previous_length, _, _ = revision_spec(predecessor)
        previous = checked(app_path(predecessor), previous_hash)
        if len(previous) != previous_length:
            raise ValueError('Unexpected previous application size')
    if (private / journal_name).exists():
        raise ValueError('Deployment already reserved; never overwrite or resume automatically')
    if revision == 61:
        from rocell.application.product_ghost_export_review import _read
        review, _ = _read(root/'runs/wizard-exports',
            'wizard-20260922T223654552605Z-59f4fa79d37b4eefac69b23d7406508e',
            'attachment-r61-visible-interval-review.json')
        if (review.get('schema') != 'rocell.r61_visible_interval_review.v1' or
                review.get('target') != 'configured-diagnostic-candidate-r61' or
                review.get('app_sha256') != expected_hash or
                review.get('app_bytes') != length or
                review.get('predecessor_sha256') != R60_HASH or
                review.get('goals') != [[2401,1713],[2389,1725],[2401,1713],[2413,1701]] or
                review.get('maximum_writes') != 4 or
                review.get('one_write_per_leg') is not True or
                review.get('retry_allowed') is not False or
                review.get('park_return_route_enabled') is not False or
                review.get('app_offset') != 0x10000 or
                review.get('app_slot_bytes') != 0x140000 or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Pinned r61 candidate review differs')
    if revision == 62:
        from rocell.application.product_ghost_export_review import _read
        review, _ = _read(root/'runs/wizard-exports',
            'wizard-20260923T010826525589Z-26620e4380964bb1a5ad694c296d5b86',
            'attachment-r62-large-pose-lift-review.json')
        if (review.get('schema') != 'rocell.r62_large_pose_lift_review.v1' or
                review.get('target') != 'configured-diagnostic-candidate-r62' or
                review.get('app_sha256') != expected_hash or
                review.get('app_bytes') != length or
                review.get('predecessor_sha256') != R61_HASH or
                review.get('synchronized_servo_ids') != [12, 13, 15] or
                review.get('targets') != [2348, 1766, 1654] or
                review.get('maximum_writes') != 1 or
                review.get('retry_allowed') is not False or
                review.get('return_allowed') is not False or
                review.get('requires_durable_export_receipt') is not True or
                review.get('app_offset') != 0x10000 or
                review.get('app_slot_bytes') != 0x140000 or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Pinned r62 candidate review differs')
    if revision == 64:
        from rocell.application.p2_lift_release import review_release
        review_release(root)
    if revision == 65:
        from rocell.application.p2_wrist_release import review_release
        review_release(root)
    if revision == 66:
        from rocell.application.p3_elbow_release import review_release
        review_release(root)
    if revision == 67:
        from rocell.application.p3_wrist_release import review_release
        review_release(root)
    if revision == 68:
        from rocell.application.t4_lift_release import review_release
        review_release(root)
    if revision == 69:
        from rocell.application.t4_wrist_release import review_release
        review_release(root)
    if revision == 70:
        from rocell.application.p4_elbow_release import review_release
        review_release(root)
    if revision == 72:
        from rocell.application.p4_repeat_release import review_release
        review_release(root)
    if revision == 73:
        from rocell.application.p4_correction_release import review_release
        review_release(root)
    if revision == 74:
        from rocell.application.p4_midpoint_release import review_release
        review_release(root)
    if revision == 75:
        from rocell.application.air_typing_release import review_release
        review_release(root)
    if revision == 76:
        from rocell.application.air_typing_b_hover_release import review_release
        review_release(root)
    if revision == 77:
        from rocell.application.air_typing_r77_release import review_release
        review_release(root)
    if revision == 78:
        from rocell.application.air_typing_r78_release import review_release
        review_release(root)
    if revision == 79:
        from rocell.application.air_typing_r79_release import review_release
        review_release(root)
    if revision == 81:
        from rocell.application.air_typing_r81_release import review_release
        review_release(root)
    if revision == 82:
        from rocell.application.air_typing_r82_release import review_release
        review_release(root)
    if revision == 83:
        from rocell.application.air_typing_r83_release import review_release
        review_release(root)
    if revision == 84:
        from rocell.application.air_typing_r84_release import review_release
        review_release(root)
    if revision == 71:
        from rocell.application.p4_wrist_release import review_release
        review_release(root)
    if revision == 63:
        from rocell.application.product_ghost_export_review import _read
        review, _ = _read(root/'runs/wizard-exports',
            'wizard-20260923T015237844562Z-190bcbdfaa974294a409e0373ce26ef6',
            'attachment-r63-large-pose-relief-review.json')
        if (review.get('schema') != 'rocell.r63_large_pose_relief_review.v1' or
                review.get('target') != 'configured-diagnostic-candidate-r63' or
                review.get('app_sha256') != expected_hash or
                review.get('app_bytes') != length or
                review.get('predecessor_sha256') != R62_HASH or
                review.get('source_pose') != 'T1' or review.get('target_pose') != 'P1' or
                review.get('synchronized_servo_ids') != [14,15] or
                review.get('targets') != [2842,1719] or
                review.get('maximum_writes') != 1 or
                review.get('retry_allowed') is not False or
                review.get('return_allowed') is not False or
                review.get('requires_durable_export_receipt') is not True or
                review.get('app_offset') != 0x10000 or
                review.get('app_slot_bytes') != 0x140000 or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Pinned r63 candidate review differs')
    if revision == 60:
        from rocell.application.product_ghost_export_review import _read
        review, _ = _read(root/'runs/wizard-exports',
            'wizard-20260922T203245596804Z-4cfdf2e1f7934171aed092479582e7be',
            'attachment-r60-policy-bound-adapter-review.json')
        if (review.get('schema') != 'rocell.r60_policy_bound_adapter_review.v1' or
                review.get('target') != 'configured-diagnostic-candidate-r60' or
                review.get('app_sha256') != expected_hash or
                review.get('app_bytes') != length or
                review.get('predecessor_sha256') != R58_HASH or
                review.get('fixed_target_goals') != [2413, 1701] or
                review.get('r58_fault_prebus_rejection_resolved') is not True or
                review.get('app_offset') != 0x10000 or
                review.get('app_slot_bytes') != 0x140000 or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Pinned r60 candidate review differs')
    if revision == 58:
        from rocell.application.product_ghost_export_review import _read
        review, _ = _read(root/'runs/wizard-exports',
            'wizard-20260922T194754620618Z-50534b00d3c94ccaa7e9f83706caeae5',
            'attachment-r58-visible-step-review.json')
        if (review.get('schema') != 'rocell.r58_visible_shoulder_step_review.v1' or
                review.get('target') != 'configured-diagnostic-candidate-r58' or
                review.get('app_sha256') != expected_hash or
                review.get('app_bytes') != length or
                review.get('predecessor_sha256') != R57_HASH or
                review.get('fixed_target_goals') != [2413, 1701] or
                review.get('app_offset') != 0x10000 or
                review.get('app_slot_bytes') != 0x140000 or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Pinned r58 candidate review differs')
    if revision == 57:
        from rocell.application.product_ghost_export_review import _read
        review, _ = _read(root/'runs/wizard-exports',
            'wizard-20260922T003202822812Z-8aa82ffd1c644837abfcc3d6609357a4',
            'attachment-r57-park-return-review.json')
        if (review.get('schema') != 'rocell.r57_park_return_review.v1' or
                review.get('target') != 'configured-diagnostic-candidate-r57' or
                review.get('app_sha256') != expected_hash or
                review.get('app_bytes') != length or
                review.get('predecessor_sha256') != R56_HASH or
                review.get('app_offset') != 0x10000 or
                review.get('app_slot_bytes') != 0x140000 or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Pinned r57 candidate review differs')
    if revision == 56:
        from rocell.application.product_ghost_export_review import _read
        review, _ = _read(root/'runs/wizard-exports',
            'wizard-20260921T234210592410Z-e54a5c2690a746fd9b7459456cf6f6d0',
            'attachment-r56-park-step-review.json')
        if (review.get('schema') != 'rocell.r56_park_step_review.v1' or
                review.get('target') != 'configured-diagnostic-candidate-r56' or
                review.get('app_sha256') != expected_hash or
                review.get('app_bytes') != length or
                review.get('predecessor_sha256') != R55_HASH or
                review.get('app_offset') != 0x10000 or
                review.get('app_slot_bytes') != 0x140000 or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Pinned r56 candidate review differs')
    if revision == 55:
        from rocell.application.product_ghost_export_review import _read
        review, _ = _read(root/'runs/wizard-exports',
            'wizard-20260921T224805390919Z-0a91a71fa008405298c821df110663af',
            'attachment-r55-park-step-review.json')
        if (review.get('schema') != 'rocell.r55_park_step_review.v1' or
                review.get('target') != 'configured-diagnostic-candidate-r55' or
                review.get('app_sha256') != expected_hash or
                review.get('app_bytes') != length or
                review.get('predecessor_sha256') != R54_HASH or
                review.get('app_offset') != 0x10000 or
                review.get('app_slot_bytes') != 0x140000 or
                review.get('reanchor_route_disabled') is not True or
                review.get('park_step_route_enabled') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Pinned r55 candidate review differs')
    if revision == 54:
        from rocell.application.product_ghost_export_review import _read
        review, _ = _read(root / 'runs/wizard-exports',
            'wizard-20260921T221053269829Z-74b79cc238f64a85ab3e8cc953be7c72',
            'attachment-r54-fixed-reanchor-review.json')
        if (review.get('schema') != 'rocell.r54_fixed_reanchor_review.v1' or
                review.get('target') != 'configured-diagnostic-candidate-r54' or
                review.get('app_sha256') != expected_hash or
                review.get('app_bytes') != length or
                review.get('predecessor_sha256') != R53_HASH or
                review.get('app_offset') != 0x10000 or
                review.get('app_slot_bytes') != 0x140000 or
                review.get('recovery_artifacts_verified') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Pinned r54 candidate review differs')
    if revision in (23, 24, 25, 26, 27, 28, 29, 31, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53):
        from rocell.application.product_ghost_export_review import _read
        review, _ = _read(root / 'runs/wizard-exports',
            {23:'wizard-20260919T183847722083Z-b678aeb19d894ca698948a169a198c85',
             24:'wizard-20260919T190009172686Z-bae43dbebbb0421eae0ffb450c050528',
             25:'wizard-20260919T194020438681Z-a684c7bfc4bc436aa129248bc7e25155',
             26:'wizard-20260919T200403483537Z-a7939864da8a496495e83327ce28caca',
             27:'wizard-20260919T202100589399Z-f1770dd8252c4a598b3cf8803e3bc4d1',
             28:'wizard-20260919T205630341948Z-7b0cc74be8584538bd92a3de82a2909e',
             29:'wizard-20260919T211631764101Z-c0dc86b394944c8a9c89846b9362c75a',
             31:'wizard-20260919T230957322878Z-6f34bf866bef4865b33f91f01e03ecea',
             33:'wizard-20260920T143032812516Z-db0af315b7104c6ab6b857ea94ab53e5',
             36:'wizard-20260920T162126924287Z-507358b7b1d44303ad72a448d8cd046f',
             37:'wizard-20260920T165240191510Z-7d095e8e200841ae9fd0036ac411a21a',
             38:'wizard-20260920T171917875430Z-2a0ed0cb7d7e4204946ca57e81dbc160',
             39:'wizard-20260920T182910494497Z-76154dbb00e04330b2b6eed869f6fb7f',
             40:'wizard-20260920T185410694745Z-9399b344b6434d32ba81c5718d567618',
             41:'wizard-20260920T191205226246Z-ee1d09ac979f445582bcdd3bd9a37416',
             42:'wizard-20260920T193204775927Z-5a61acd29ce945859a551e99b93121f1',
             43:'wizard-20260920T194546707012Z-b8c32ef012224eb193a00565332fca2e',
             44:'wizard-20260920T201138154080Z-45b1e4acd6c1447eb5e11b7db94862db',
             45:'wizard-20260920T201139668664Z-ef44c6bcac254e6bb907258b3b923cf2',
             46:'wizard-20260920T205529221817Z-b2496f89ae384f439878d7a7d3ee09dc',
             47:'wizard-20260920T205530940952Z-6c8e518625804964838aea735d71e768',
             48:'wizard-20260920T213308029747Z-8b3fbead82f44e5c84eeafa41c6a1843',
             49:'wizard-20260920T220532774591Z-a2b11b514039439f88d74896432fabb9',
             50:'wizard-20260921T020230782394Z-2434980751944f1698896e49d76415a9',
             51:'wizard-20260921T031043920855Z-da5c6305db944ba1a889bf28c6816e5a',
             52:'wizard-20260921T095000154047Z-7509bcd94555463a86eae274d9e8b6f0',
             53:'wizard-20260921T192611219874Z-692de670df434dc5a509ea921aa22b0a',
             35:'wizard-20260920T155528364009Z-a5c2612298c14630b8b3b8ee32c95c54',
             34:'wizard-20260920T145114719151Z-3b726b92be3b4c3b81ee8f29bebb8751'}[revision],
            'attachment-pair-candidate-review.json')
        if (review['target'] != f'configured-diagnostic-candidate-r{revision}'
                or review['artifacts']['RoArm-M3_example.ino.bin'] != dict(sha256=expected_hash, bytes=length)
                or review['app_offset'] != 0x10000 or review['app_slot_bytes'] != 0x140000
                or review['hardware_access'] is not False or review['firmware_uploaded'] is not False):
            raise ValueError('Pinned candidate review differs')
    if revision in (22, 23, 24, 25, 26, 27, 28, 29, 31, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72,73,74,75,76,77,78,79,81,82,83,84):
        from rocell.application.observed_pose_installation import review_observed_installation
        from rocell.providers.windows.diagnostic_image_store import load_image
        review = review_observed_installation(root,
            stage_export='wizard-20260919T145415048349Z-1324830e574a4e9294c0302ecce85e39',
            installation_export='wizard-20260919T151102041680Z-273348d615584d5595ec7dcf92acd265')
        filesystem = load_image(private / 'observed-pose-plus10-candidate.dpapi')
        expected_fs = '45320bab56ec1d8e889078a50e2aa0ef79d4d65c59e5dcb89c7a7880f08e7267'
        if (review['candidate_sha256'] != expected_fs or len(filesystem) != 0x160000
                or hashlib.sha256(filesystem).hexdigest() != expected_fs):
            raise ValueError('Observed-pose filesystem differs')
    elif revision in (17, 19, 20, 21):
        from rocell.application.negative_pair_provisioning import review_negative_installation
        from rocell.providers.windows.diagnostic_image_store import load_image
        review_negative_installation(root, 'wizard-20260919T122314132214Z-9a1e2bb36ed8412cb54610a1ca58fa9f')
        filesystem = load_image(private / 'pair-negative6-candidate.dpapi')
        if (len(filesystem) != 0x160000 or hashlib.sha256(filesystem).hexdigest() !=
                'd1c041bcb4e90082685babc16698bcef3c639d87464932d6534d8056b71ce3aa'):
            raise ValueError('Negative-direction filesystem differs')
    elif revision in (11,12,13,14,16):
        filesystem = pair_settings_filesystem(root, private)
    elif revision == 10:
        filesystem = supported_pose_filesystem(root, private)
    elif revision == 7:
        filesystem = provisioned_filesystem(root, private)
    else:
        filesystem = backup[0x290000:0x3f0000]
    return dict(app=app, private=private, image=image, backup=backup, previous=previous,
        filesystem_md5=hashlib.md5(filesystem).hexdigest(),
        filesystem_sha256=hashlib.sha256(filesystem).hexdigest(),
        expected_hash=expected_hash, journal_name=journal_name)


def verified_stream(image, name):
    # Flash the exact bytes checked in preflight, not a later reopening of a path.
    stream = io.BytesIO(image)
    stream.name = str(name)
    return stream


def verify_installed_predecessor(stub, prepared):
    """Read-only prewrite checks; callers must not write after any mismatch."""
    previous, backup = prepared['previous'], prepared['backup']
    checks = (
        (0x10000, len(previous), hashlib.md5(previous).hexdigest(),
         'Installed app differs from expected predecessor'),
        (0x8000, 3072, hashlib.md5(backup[0x8000:0x8c00]).hexdigest(),
         'Installed partition table changed'),
        (0x290000, 0x160000, prepared['filesystem_md5'],
         'Filesystem changed since reviewed snapshot'),
    )
    for start, length, expected, message in checks:
        if stub.flash_md5sum(start, length) != expected:
            raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--authorized-app-only-and-startup', action='store_true')
    mode.add_argument('--preflight-only', action='store_true', help='Verify local artifacts only; no hardware access')
    parser.add_argument('--revision', type=int, choices=(2, 3, 6, 7, 10, 11, 12, 13, 14, 16, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72,73,74,75,76,77,78,79,81,82,83,84), default=2)
    parser.add_argument('--approved-r27-second-attempt', action='store_true',
                        help='Separate approved attempt; preserve the first failed journal')
    parser.add_argument('--approved-r42-second-attempt', action='store_true',
                        help='Separate approved attempt after the exact prewrite r42 failure')
    parser.add_argument('--approved-r64-second-attempt', action='store_true',
                        help='Separate authorized recovery after the exact r64 prewrite failure')
    parser.add_argument('--approved-r69-second-attempt', action='store_true',
                        help='Separate authorized recovery after the exact r69 prewrite failure')
    options = parser.parse_args()
    if sum((options.approved_r27_second_attempt, options.approved_r42_second_attempt,
            options.approved_r64_second_attempt, options.approved_r69_second_attempt)) > 1:
        parser.error('Select at most one separate-attempt authorization')
    if options.approved_r64_second_attempt and options.revision != 64:
        parser.error('r64 recovery authorization requires revision 64')
    if options.approved_r69_second_attempt and options.revision != 69:
        parser.error('r69 recovery authorization requires revision 69')
    root = Path(__file__).resolve().parents[1]
    second_attempt = (options.approved_r27_second_attempt or options.approved_r42_second_attempt
                      or options.approved_r64_second_attempt or options.approved_r69_second_attempt)
    prepared = preflight(root, options.revision, second_attempt=second_attempt)
    app, private = prepared['app'], prepared['private']
    image, backup, previous = prepared['image'], prepared['backup'], prepared['previous']
    expected_hash, journal_name = prepared['expected_hash'], prepared['journal_name']
    if options.preflight_only:
        print(json.dumps(dict(status='LOCAL_PREFLIGHT_VERIFIED', revision=options.revision,
            app_sha256=expected_hash, app_bytes=len(image), predecessor_sha256=hashlib.sha256(previous).hexdigest(),
            expected_filesystem_sha256=prepared['filesystem_sha256'],
            journal_reserved=False, hardware_access=False, deployment_authorized=False)))
        return
    sys.path.insert(0, str(root / '.firmware-tools/esptool-api-4.6'))
    import esptool
    from esptool import cmds, loader
    import serial
    if (esptool.__version__ != '4.6' or not Path(esptool.__file__).resolve().is_relative_to(
            (root / '.firmware-tools/esptool-api-4.6').resolve())):
        raise ValueError('Unexpected esptool version')
    if second_attempt or options.revision in (28,29,31,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,81,82,83,84):
        from serial.tools.list_ports import comports
        matches = [p for p in comports() if p.device == 'COM7' and p.vid == 0x10c4
                   and p.pid == 0xea60 and p.serial_number == '52E4E1E8337FEF119E92181CEDD322A4']
        if len(matches) != 1:
            raise ValueError('Expected USB adapter not identified')
    # The vendor default retries writes. Approved procedure stops on first failure.
    loader.WRITE_BLOCK_ATTEMPTS = 1
    with (private / journal_name).open('x', encoding='utf-8') as journal:
        def event(stage, **fields):
            entry = dict(stage=stage, **fields)
            journal.write(json.dumps(entry) + '\n')
            journal.flush()
            os.fsync(journal.fileno())
            print(json.dumps(entry), flush=True)

        event('RESERVED', app_sha256=expected_hash, offset=65536, bytes=len(image))
        port = serial.Serial(port=None, baudrate=115200, timeout=3, write_timeout=10)
        port.dtr = False
        port.rts = False
        port.port = 'COM7'
        try:
            port.open()
            esp = (longer_reset_rom(esptool, port) if second_attempt or options.revision in (28,29,31,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,81,82,83,84)
                   else esptool.ESP32ROM(port, baud=115200))
            esp.connect('default_reset', attempts=1)
            mac = ':'.join(f'{v:02x}' for v in esp.read_mac())
            if mac != 'fc:e8:c0:f8:d5:38':
                raise ValueError('Controller identity mismatch')
            if esp.secure_download_mode or esp.stub_is_disabled or esp.get_secure_boot_enabled() or esp.get_flash_encryption_enabled():
                raise ValueError('Security state incompatible with reviewed deployment')
            stub = esp.run_stub()
            if stub.flash_id() != 0x164020:
                raise ValueError('Unexpected flash identity')
            verify_installed_predecessor(stub, prepared)
            # Before/after digests prove the write did not touch other partitions.
            protected = [(0, 0x10000), (0x150000, 0x2b0000)]
            before = [stub.flash_md5sum(start, size) for start, size in protected]
            event('IDENTITY_AND_PREWRITE_VERIFIED', mac=mac)
            with verified_stream(image, app) as stream:
                args = SimpleNamespace(addr_filename=[(0x10000, stream)],
                    compress=True, no_compress=False, no_stub=False, force=False,
                    encrypt=False, encrypt_files=None, erase_all=False, verify=False,
                    ignore_flash_encryption_efuse_setting=False,
                    flash_size='keep', flash_mode='keep', flash_freq='keep')
                event('WRITE_ATTEMPT_STARTED')
                cmds.write_flash(stub, args)
            # Independent full app readback with stream integrity plus SHA-256.
            readback = stub.read_flash(0x10000, len(image))
            if readback != image:
                raise ValueError('Application readback mismatch')
            after = [stub.flash_md5sum(start, size) for start, size in protected]
            if before != after:
                raise ValueError('Protected region changed during deployment')
            event('FLASH_VERIFIED', app_sha256=hashlib.sha256(readback).hexdigest(),
                  protected_regions_unchanged=True)
            event('ONE_STARTUP_ATTEMPT')
            stub.hard_reset()
            event('STARTUP_RESET_SENT', application_health_verified=False)
        except BaseException as error:
            event('STOPPED', error_type=type(error).__name__, error=str(error), retry=False)
            raise
        finally:
            port.close()


if __name__ == '__main__':
    main()

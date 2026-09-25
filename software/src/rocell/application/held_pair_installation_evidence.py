"""Read-only r10 installation evidence from the one-use installer journal.

This proves what the retained host journal reports, not current device bytes,
startup health, pair provisioning or permission to move. It never opens a port.
"""
import hashlib
import json
from pathlib import Path

from .first_motion_contract import canonical
from .physical_onboarding_durability import read_bounded_regular_file
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter
from .wizard_held_pair import R10_APP_SHA256

APP_BYTES=1103808
JOURNAL='app-r10-deployment-events.jsonl'
REVIEW='wizard-20260919T012725080913Z-5b946c1dd7eb44e6b8e09626ccb27d32'


def _profile(revision):
    if type(revision) is not int or revision not in (10, 11, 12, 13, 14, 16, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72,73,74,75,76,77,78,79,81,82,83,84):
        raise ValueError('Reviewed installation revision required')
    if revision == 10:
        return R10_APP_SHA256, APP_BYTES, JOURNAL, REVIEW
    if revision == 67:
        from .p3_wrist_release import APP_SHA, APP_BYTES as R67_BYTES, REVIEW as R67_REVIEW
        return APP_SHA, R67_BYTES, 'app-r67-deployment-events.jsonl', R67_REVIEW
    if revision == 68:
        from .t4_lift_release import APP_SHA, APP_BYTES as R68_BYTES, REVIEW as R68_REVIEW
        return APP_SHA, R68_BYTES, 'app-r68-deployment-events.jsonl', R68_REVIEW
    if revision == 69:
        from .t4_wrist_release import APP_SHA, APP_BYTES as R69_BYTES, REVIEW as R69_REVIEW
        return APP_SHA, R69_BYTES, 'app-r69-attempt2-deployment-events.jsonl', R69_REVIEW
    if revision == 70:
        from .p4_elbow_release import APP_SHA, APP_BYTES as R70_BYTES, REVIEW as R70_REVIEW
        return APP_SHA, R70_BYTES, 'app-r70-deployment-events.jsonl', R70_REVIEW
    if revision == 72:
        from .p4_repeat_release import APP_SHA, APP_BYTES as R72_BYTES, REVIEW as R72_REVIEW
        return APP_SHA, R72_BYTES, 'app-r72-deployment-events.jsonl', R72_REVIEW
    if revision == 73:
        from .p4_correction_release import APP_SHA, APP_BYTES as R73_BYTES, REVIEW as R73_REVIEW
        return APP_SHA, R73_BYTES, 'app-r73-deployment-events.jsonl', R73_REVIEW
    if revision == 74:
        from .p4_midpoint_release import APP_SHA, APP_BYTES as R74_BYTES, REVIEW as R74_REVIEW
        return APP_SHA, R74_BYTES, 'app-r74-deployment-events.jsonl', R74_REVIEW
    if revision == 75:
        from .air_typing_release import APP_SHA, APP_BYTES as R75_BYTES, REVIEW as R75_REVIEW
        return APP_SHA, R75_BYTES, 'app-r75-deployment-events.jsonl', R75_REVIEW
    if revision == 76:
        from .air_typing_b_hover_release import APP_SHA, APP_BYTES as R76_BYTES, REVIEW as R76_REVIEW
        return APP_SHA, R76_BYTES, 'app-r76-deployment-events.jsonl', R76_REVIEW
    if revision == 77:
        from .air_typing_r77_release import APP_SHA, APP_BYTES as R77_BYTES, REVIEW as R77_REVIEW
        return APP_SHA, R77_BYTES, 'app-r77-deployment-events.jsonl', R77_REVIEW
    if revision == 78:
        from .air_typing_r78_release import APP_SHA, APP_BYTES as R78_BYTES, REVIEW as R78_REVIEW
        return APP_SHA, R78_BYTES, 'app-r78-deployment-events.jsonl', R78_REVIEW
    if revision == 79:
        from .air_typing_r79_release import APP_SHA, APP_BYTES as R79_BYTES, REVIEW as R79_REVIEW
        return APP_SHA, R79_BYTES, 'app-r79-deployment-events.jsonl', R79_REVIEW
    if revision == 81:
        from .air_typing_r81_release import APP_SHA, APP_BYTES as R81_BYTES, REVIEW as R81_REVIEW
        return APP_SHA, R81_BYTES, 'app-r81-deployment-events.jsonl', R81_REVIEW
    if revision == 82:
        from .air_typing_r82_release import APP_SHA, APP_BYTES as R82_BYTES, REVIEW as R82_REVIEW
        return APP_SHA, R82_BYTES, 'app-r82-deployment-events.jsonl', R82_REVIEW
    if revision == 83:
        from .air_typing_r83_release import APP_SHA, APP_BYTES as R83_BYTES, REVIEW as R83_REVIEW
        return APP_SHA, R83_BYTES, 'app-r83-deployment-events.jsonl', R83_REVIEW
    if revision == 84:
        from .air_typing_r84_release import APP_SHA, APP_BYTES as R84_BYTES, REVIEW as R84_REVIEW
        return APP_SHA, R84_BYTES, 'app-r84-deployment-events.jsonl', R84_REVIEW
    if revision == 71:
        from .p4_wrist_release import APP_SHA, APP_BYTES as R71_BYTES, REVIEW as R71_REVIEW
        return APP_SHA, R71_BYTES, 'app-r71-deployment-events.jsonl', R71_REVIEW
    if revision == 66:
        from .p3_elbow_release import APP_SHA, APP_BYTES as R66_BYTES, REVIEW as R66_REVIEW
        return APP_SHA, R66_BYTES, 'app-r66-deployment-events.jsonl', R66_REVIEW
    if revision == 65:
        from .p2_wrist_release import APP_SHA, APP_BYTES as R65_BYTES, REVIEW as R65_REVIEW
        return APP_SHA, R65_BYTES, 'app-r65-deployment-events.jsonl', R65_REVIEW
    if revision == 64:
        from .p2_lift_release import APP_SHA, APP_BYTES as R64_BYTES, REVIEW as R64_REVIEW
        return APP_SHA, R64_BYTES, 'app-r64-attempt2-deployment-events.jsonl', R64_REVIEW
    if revision == 63:
        return ('cbca0f164c49f480c282fe2ed435616a50a767db50b1048b24b7abb40e55604b',
                1200704, 'app-r63-deployment-events.jsonl',
                'wizard-20260923T015237844562Z-190bcbdfaa974294a409e0373ce26ef6')
    if revision == 62:
        return ('ee259799cb6b74b80cc4a45e16934ac6476b81d7a4536cc31406fffb766fd6e4',
                1192368, 'app-r62-deployment-events.jsonl',
                'wizard-20260923T010826525589Z-26620e4380964bb1a5ad694c296d5b86')
    if revision == 61:
        return ('5f713ae53577b3a4dc6a6419f2a3b84563b2db89f903be9c24bc496482f41451',
                1183616, 'app-r61-deployment-events.jsonl',
                'wizard-20260922T223654552605Z-59f4fa79d37b4eefac69b23d7406508e')
    if revision == 60:
        return ('6f98f372b5a927b016ae81f0673df1ee8ddd0f0b78bc714d181746e575df7211',
                1183360, 'app-r60-deployment-events.jsonl',
                'wizard-20260922T203245596804Z-4cfdf2e1f7934171aed092479582e7be')
    if revision == 58:
        return ('944155ce47d2eeb60e6c7e7cb12d687a9250c6b3c030de49d39c9e923dc544f5',
                1183232, 'app-r58-deployment-events.jsonl',
                'wizard-20260922T194754620618Z-50534b00d3c94ccaa7e9f83706caeae5')
    if revision == 57:
        return ('7d8ac14ae59272368fbf3031ebc3ad5a5835e84913d85ee5758df46670767b68',
                1183296, 'app-r57-deployment-events.jsonl',
                'wizard-20260922T003202822812Z-8aa82ffd1c644837abfcc3d6609357a4')
    if revision == 56:
        return ('09864d144d630b2655c78956b0ea8148b0525bcdef017caa843d74f1f4661e79',
                1175728, 'app-r56-deployment-events.jsonl',
                'wizard-20260921T234210592410Z-e54a5c2690a746fd9b7459456cf6f6d0')
    if revision == 55:
        return ('1ea884af0cd717775c67046302ab5e9df82b9514b552b96fc8d27d5ad853d9a5',
                1175216, 'app-r55-deployment-events.jsonl',
                'wizard-20260921T224805390919Z-0a91a71fa008405298c821df110663af')
    if revision == 54:
        return ('c418af3062200c91e6cdf4c5540a7e251f09cdc36fccb9659a9b9a6181f818fe',
                1167056, 'app-r54-deployment-events.jsonl',
                'wizard-20260921T221053269829Z-74b79cc238f64a85ab3e8cc953be7c72')
    if revision == 53:
        return ('8d5ed3f0feb491e2294bb6f56bf27f82c53f616d257c61f493df58d94f050de5',
                1159392, 'app-r53-deployment-events.jsonl',
                'wizard-20260921T192611219874Z-692de670df434dc5a509ea921aa22b0a')
    if revision == 52:
        return ('0389e22b97cb9e87a97dc4491746af385d3dfcf76c00daaaab434a36b088738b',
                1159328, 'app-r52-deployment-events.jsonl',
                'wizard-20260921T095000154047Z-7509bcd94555463a86eae274d9e8b6f0')
    if revision == 51:
        return ('0a45c55ace66374038c712672bee41b507a80e64a121b0a020b4836ce2bddc9e',
                1158992, 'app-r51-deployment-events.jsonl',
                'wizard-20260921T031043920855Z-da5c6305db944ba1a889bf28c6816e5a')
    if revision == 50:
        return ('0dda0988222a1de534a5d72de1f528f6ae42fed5be0215fed8fbd75129e6121b',
                1158736, 'app-r50-deployment-events.jsonl',
                'wizard-20260921T020230782394Z-2434980751944f1698896e49d76415a9')
    if revision == 49:
        return ('e4b331623527aa94078e514f8cd37e18ac00a04bf543b9005072ff677a42c21f',
                1158528, 'app-r49-deployment-events.jsonl',
                'wizard-20260920T220532774591Z-a2b11b514039439f88d74896432fabb9')
    if revision == 48:
        return ('e76470e40216c39dd6ebc57df3e665c50fa6436da680bbeea0b18c599deddc1b',
                1158256, 'app-r48-deployment-events.jsonl',
                'wizard-20260920T213308029747Z-8b3fbead82f44e5c84eeafa41c6a1843')
    if revision == 47:
        return ('a2101ea8ec27b7f9c93063b3e5dea91546b91b2edfbca63b3cc5e71f3f7cee1e',
                1157936, 'app-r47-deployment-events.jsonl',
                'wizard-20260920T205530940952Z-6c8e518625804964838aea735d71e768')
    if revision == 46:
        return ('1b205cffb023761f228be728a8caee9de0e13b17751d4bec28b6ba5584c83d87',
                1157936, 'app-r46-deployment-events.jsonl',
                'wizard-20260920T205529221817Z-b2496f89ae384f439878d7a7d3ee09dc')
    if revision == 45:
        return ('3b9e5930b9818ee4c4425541f6100d8dc22320eadd883f9d4391ff8499487af6',
                1157616, 'app-r45-deployment-events.jsonl',
                'wizard-20260920T201139668664Z-ef44c6bcac254e6bb907258b3b923cf2')
    if revision == 44:
        return ('f1910697b4653c941974e9dc9939357ccfe7a7016c526285465decdea2614d7d',
                1157616, 'app-r44-deployment-events.jsonl',
                'wizard-20260920T201138154080Z-45b1e4acd6c1447eb5e11b7db94862db')
    if revision == 43:
        return ('459e1f31ac103c634b2205654501693d9116bded2bcd9ac1bf8de5284a20fb1b',
                1156992, 'app-r43-deployment-events.jsonl',
                'wizard-20260920T194546707012Z-b8c32ef012224eb193a00565332fca2e')
    if revision == 42:
        return ('6d3405b3b42db9347ec02445b0937886ca0fba82bf38d905e3989ad48c8f71ea',
                1156992, 'app-r42-attempt2-deployment-events.jsonl',
                'wizard-20260920T193204775927Z-5a61acd29ce945859a551e99b93121f1')
    if revision == 41:
        return ('caa26535377b8f35e3bfdc8d0546c779db052a520a355eaab455dcf64defc5cf',
                1156992, 'app-r41-deployment-events.jsonl',
                'wizard-20260920T191205226246Z-ee1d09ac979f445582bcdd3bd9a37416')
    if revision == 40:
        return ('0bdfad949388b758fff3b8b177a24c9da87e7089ed6a952c6a03b6daf9833213',
                1156384, 'app-r40-deployment-events.jsonl',
                'wizard-20260920T185410694745Z-9399b344b6434d32ba81c5718d567618')
    if revision == 39:
        return ('590a2f942214e9830fdfda9ad9610cf4c71c9fec818aa3dacabc02a6291f1156',
                1156384, 'app-r39-deployment-events.jsonl',
                'wizard-20260920T182910494497Z-76154dbb00e04330b2b6eed869f6fb7f')
    if revision == 38:
        return ('eee1b0f9b8b835573e0237f830108e2f4ead3f88efc3a11651401c7130f0d92e',
                1156048, 'app-r38-deployment-events.jsonl',
                'wizard-20260920T171917875430Z-2a0ed0cb7d7e4204946ca57e81dbc160')
    if revision == 37:
        return ('24a3f58df32b5c3db77a6952ed22bf1eddc79c535760afc90abcc67d8e8806ee',
                1156080, 'app-r37-deployment-events.jsonl',
                'wizard-20260920T165240191510Z-7d095e8e200841ae9fd0036ac411a21a')
    if revision == 36:
        return ('1e8564d204aa773149ad54fc58fd70bee294bdfdea74e8d29b2f07de19417dfd',
                1155600, 'app-r36-deployment-events.jsonl',
                'wizard-20260920T162126924287Z-507358b7b1d44303ad72a448d8cd046f')
    if revision == 35:
        return ('c34ebe285db2e31be5c0f4ed35497cd13c280c82a130ac690e120c23f94cda91',
                1155456, 'app-r35-deployment-events.jsonl',
                'wizard-20260920T155528364009Z-a5c2612298c14630b8b3b8ee32c95c54')
    if revision == 34:
        return ('6637e0e6f06b731db23621d8a727cdc0f9b82a2473813eec9a3b8a98fbd09945',
                1155184, 'app-r34-deployment-events.jsonl',
                'wizard-20260920T145114719151Z-3b726b92be3b4c3b81ee8f29bebb8751')
    if revision == 33:
        return ('170188fe380cc7a21ee5502e831f21c3050b34768bdbbbbc1ddf7f7e608b330d',
                1154048, 'app-r33-deployment-events.jsonl',
                'wizard-20260920T143032812516Z-db0af315b7104c6ab6b857ea94ab53e5')
    if revision == 31:
        return ('e8400d1c302a70bed3283c4102fa6b202785c1ea35826de2e98754a09b80fae3',
                1150592, 'app-r31-deployment-events.jsonl',
                'wizard-20260919T230957322878Z-6f34bf866bef4865b33f91f01e03ecea')
    if revision == 29:
        return ('d9d61fc6bcc3b32b6e84a6d3065dcd6bbbf96d374243b83fb140c9e5395baa00',
                1146336, 'app-r29-deployment-events.jsonl',
                'wizard-20260919T211631764101Z-c0dc86b394944c8a9c89846b9362c75a')
    if revision == 28:
        return ('88ccd20ebb1607a130cc25f6c5026690cd258cb14ba0d1b0bd763f32540f232e',
                1145728, 'app-r28-deployment-events.jsonl',
                'wizard-20260919T205630341948Z-7b0cc74be8584538bd92a3de82a2909e')
    if revision == 27:
        return ('c46e1ab78cb6b38c1244f1da8dd8b459340704b65af093c3b1875ed3d6158bba',
                1145280, 'app-r27-attempt2-deployment-events.jsonl',
                'wizard-20260919T202100589399Z-f1770dd8252c4a598b3cf8803e3bc4d1')
    if revision == 26:
        return ('2a17bdf5a24cb1a3032d0212ca3c2db11d1f6a5b2027fdaf45b44f9c5e4f3c78',
                1143376, 'app-r26-deployment-events.jsonl',
                'wizard-20260919T200403483537Z-a7939864da8a496495e83327ce28caca')
    if revision == 25:
        return ('483604c16de0b2061335873fdc176b90551e16e7552fcd2aa6058e6449bbde5f',
                1142688, 'app-r25-deployment-events.jsonl',
                'wizard-20260919T194020438681Z-a684c7bfc4bc436aa129248bc7e25155')
    if revision == 24:
        return ('fe3eaec72bb31f72210bec45912b8d5bb4df27adcb292a94decf15106a9436be',
                1141424, 'app-r24-deployment-events.jsonl',
                'wizard-20260919T190009172686Z-bae43dbebbb0421eae0ffb450c050528')
    if revision == 23:
        return ('9edf6bbcf1052a8191d7ecac37195867bb8fafd0149bcaecf585834c807f579b',
                1141360, 'app-r23-deployment-events.jsonl',
                'wizard-20260919T183847722083Z-b678aeb19d894ca698948a169a198c85')
    if revision == 22:
        return ('047beb3ac792a2c5f85c2b10138d0ca9bd47ae80359af7312138e56f0d132679',
                1129648, 'app-r22-deployment-events.jsonl',
                'wizard-20260919T172516138131Z-f0115efad48f4fd7b8b20ef60d7e96bb')
    if revision == 21:
        return ('035922452587280362fc1e6fe0120f274647eeb2b0f8ee3c7bc88cb8c3289051',
                1127424, 'app-r21-deployment-events.jsonl',
                'wizard-20260919T142847003629Z-01aecbc603a44160b7939da5f8545677')
    if revision == 20:
        return ('188e7a96ef11e516655f2f8b9e3efeecb4947a501bdc1ae2beda5cffb5da9572',
                1127072, 'app-r20-deployment-events.jsonl',
                'wizard-20260919T135301585758Z-88cd5f3bb83a49ffa7373e76fd7ef4ff')
    if revision == 19:
        return ('18d5586456f4d3552b88edcd3770c6c97677aacfce66eb6dcc33cd2b2914f8ce',
                1122896, 'app-r19-deployment-events.jsonl',
                'wizard-20260919T131942528137Z-def7200ffc95431e902944799a079231')
    if revision == 17:
        return ('0ed01a2294b19047d95aeeeaf48af6c12d5610128cebe0bd94ca4119ccd5715b',
                1122416, 'app-r17-deployment-events.jsonl',
                'wizard-20260919T124054166083Z-399e1eb0287e4e47a30bd9409a3469aa')
    if revision == 16:
        return ('dc8b6f0016d29495ef6403d6a04adcbc192ec45ccd1ede7c390c3d1b4b3ea05e',
                1120240, 'app-r16-deployment-events.jsonl',
                'wizard-20260919T113432413777Z-e84ef889a4df40b8bb58f3fdc2a7c827')
    if revision == 14:
        return ('83ad71a221168ae59c65fc711f781ba6532a996b9b9d28464647ca19e0441281',
                1106528, 'app-r14-deployment-events.jsonl',
                'wizard-20260919T041556699854Z-bcd5e94f20c3470c84479dcbf941d91e')
    if revision == 13:
        return ('4503aaa00409624ebc0a54876c45eec5af684a6717327046d34a5e7c644b9a6e',
                1104048, 'app-r13-deployment-events.jsonl',
                'wizard-20260919T031040134363Z-d30ef69cb3924c718e1206385bd04545')
    if revision == 12:
        return ('81227435b8d6b3e36da8e43cd06e88b7d5872e6fc6566eb8d0a5b9a69d7da41d',
                1103920, 'app-r12-deployment-events.jsonl',
                'wizard-20260919T025602273432Z-9146856eb72d43a59ff831b8d67b2254')
    return ('52979050aa4fabbe167f01fc1bb7b656105cb370d54f3dd9890c5f6703682b52',
            1103872, 'app-r11-deployment-events.jsonl',
            'wizard-20260919T023155403856Z-39819880642a4b73ac23ab5198c64b15')


def _decode_journal(raw, *, revision=10):
    app_hash, app_bytes, _, _ = _profile(revision)
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate deployment event field')
            result[key]=value
        return result
    try:
        rows=[json.loads(line,object_pairs_hook=unique) for line in raw.decode('utf-8').splitlines()]
    except (UnicodeError,json.JSONDecodeError) as error:
        raise ValueError('Malformed deployment journal') from error
    expected=[
        dict(stage='RESERVED',app_sha256=app_hash,offset=0x10000,bytes=app_bytes),
        dict(stage='IDENTITY_AND_PREWRITE_VERIFIED',mac='fc:e8:c0:f8:d5:38'),
        dict(stage='WRITE_ATTEMPT_STARTED'),
        dict(stage='FLASH_VERIFIED',app_sha256=app_hash,protected_regions_unchanged=True),
        dict(stage='ONE_STARTUP_ATTEMPT'),
        dict(stage='STARTUP_RESET_SENT',application_health_verified=False),
    ]
    # Canonical bytes distinguish bools from integers and reject extra fields,
    # duplicate/resumed attempts, STOPPED entries and incomplete histories.
    if canonical(rows)!=canonical(expected):
        raise ValueError('Exact completed r10 app-only journal required')
    return rows


def review_pair_installation(software_root, *, revision=10):
    app_hash, app_bytes, journal_name, review_id = _profile(revision)
    root=Path(software_root).resolve()
    journal=root/'private-backups/controller-20260918-session1'/journal_name
    raw=read_bounded_regular_file(journal,maximum_bytes=16384)
    rows=_decode_journal(raw, revision=revision)
    if revision == 72:
        from .p4_repeat_release import review_release
        review,review_sha=review_release(root)
    elif revision == 73:
        from .p4_correction_release import review_release
        review,review_sha=review_release(root)
    elif revision == 74:
        from .p4_midpoint_release import review_release
        review,review_sha=review_release(root)
    elif revision == 75:
        from .air_typing_release import review_release
        review,review_sha=review_release(root)
    elif revision == 76:
        from .air_typing_b_hover_release import review_release
        review,review_sha=review_release(root)
    elif revision == 77:
        from .air_typing_r77_release import review_release
        review,review_sha=review_release(root)
    elif revision == 78:
        from .air_typing_r78_release import review_release
        review,review_sha=review_release(root)
    elif revision == 79:
        from .air_typing_r79_release import review_release
        review,review_sha=review_release(root)
    elif revision == 81:
        from .air_typing_r81_release import review_release
        review,review_sha=review_release(root)
    elif revision == 82:
        from .air_typing_r82_release import review_release
        review,review_sha=review_release(root)
    elif revision == 83:
        from .air_typing_r83_release import review_release
        review,review_sha=review_release(root)
    elif revision == 84:
        from .air_typing_r84_release import review_release
        review,review_sha=review_release(root)
    elif revision == 71:
        from .p4_wrist_release import review_release
        review,review_sha=review_release(root)
    elif revision == 70:
        from .p4_elbow_release import review_release
        review,review_sha=review_release(root)
    elif revision == 69:
        from .t4_wrist_release import review_release
        review,review_sha=review_release(root)
    elif revision == 68:
        from .t4_lift_release import review_release
        review,review_sha=review_release(root)
    elif revision == 67:
        from .p3_wrist_release import review_release
        review,review_sha=review_release(root)
    elif revision == 66:
        from .p3_elbow_release import review_release
        review,review_sha=review_release(root)
    elif revision == 65:
        from .p2_wrist_release import review_release
        review,review_sha=review_release(root)
    elif revision == 64:
        from .p2_lift_release import review_release
        review,review_sha=review_release(root)
    elif revision == 63:
        review,review_sha=_read(root/'runs/wizard-exports',review_id,
                                'attachment-r63-large-pose-relief-review.json')
        if (review.get('schema')!='rocell.r63_large_pose_relief_review.v1' or
                review.get('target')!='configured-diagnostic-candidate-r63' or
                review.get('app_sha256')!=app_hash or review.get('app_bytes')!=app_bytes or
                review.get('app_offset')!=0x10000 or review.get('app_slot_bytes')!=0x140000 or
                review.get('predecessor_sha256')!=
                    'ee259799cb6b74b80cc4a45e16934ac6476b81d7a4536cc31406fffb766fd6e4' or
                review.get('source_pose')!='T1' or review.get('target_pose')!='P1' or
                review.get('synchronized_servo_ids')!=[14,15] or
                review.get('targets')!=[2842,1719] or
                review.get('maximum_writes')!=1 or
                review.get('retry_allowed') is not False or
                review.get('return_allowed') is not False or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Reviewed r63 candidate evidence differs')
    elif revision == 62:
        review,review_sha=_read(root/'runs/wizard-exports',review_id,
                                'attachment-r62-large-pose-lift-review.json')
        if (review.get('schema')!='rocell.r62_large_pose_lift_review.v1' or
                review.get('target')!='configured-diagnostic-candidate-r62' or
                review.get('app_sha256')!=app_hash or review.get('app_bytes')!=app_bytes or
                review.get('app_offset')!=0x10000 or review.get('app_slot_bytes')!=0x140000 or
                review.get('predecessor_sha256')!=
                    '5f713ae53577b3a4dc6a6419f2a3b84563b2db89f903be9c24bc496482f41451' or
                review.get('synchronized_servo_ids')!=[12,13,15] or
                review.get('targets')!=[2348,1766,1654] or
                review.get('maximum_writes')!=1 or
                review.get('retry_allowed') is not False or
                review.get('return_allowed') is not False or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Reviewed r62 candidate evidence differs')
    elif revision == 61:
        review,review_sha=_read(root/'runs/wizard-exports',review_id,
                                'attachment-r61-visible-interval-review.json')
        if (review.get('schema')!='rocell.r61_visible_interval_review.v1' or
                review.get('target')!='configured-diagnostic-candidate-r61' or
                review.get('app_sha256')!=app_hash or review.get('app_bytes')!=app_bytes or
                review.get('app_offset')!=0x10000 or review.get('app_slot_bytes')!=0x140000 or
                review.get('predecessor_sha256')!=
                    '6f98f372b5a927b016ae81f0673df1ee8ddd0f0b78bc714d181746e575df7211' or
                review.get('goals')!=[[2401,1713],[2389,1725],[2401,1713],[2413,1701]] or
                review.get('maximum_writes')!=4 or
                review.get('one_write_per_leg') is not True or
                review.get('retry_allowed') is not False or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Reviewed r61 candidate evidence differs')
    elif revision == 60:
        review,review_sha=_read(root/'runs/wizard-exports',review_id,
                                'attachment-r60-policy-bound-adapter-review.json')
        if (review.get('schema')!='rocell.r60_policy_bound_adapter_review.v1' or
                review.get('target')!='configured-diagnostic-candidate-r60' or
                review.get('app_sha256')!=app_hash or review.get('app_bytes')!=app_bytes or
                review.get('app_offset')!=0x10000 or review.get('app_slot_bytes')!=0x140000 or
                review.get('predecessor_sha256')!=
                    '944155ce47d2eeb60e6c7e7cb12d687a9250c6b3c030de49d39c9e923dc544f5' or
                review.get('fixed_target_goals')!=[2413,1701] or
                review.get('r58_fault_prebus_rejection_resolved') is not True or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Reviewed r60 candidate evidence differs')
    elif revision == 58:
        review,review_sha=_read(root/'runs/wizard-exports',review_id,
                                'attachment-r58-visible-step-review.json')
        if (review.get('schema')!='rocell.r58_visible_shoulder_step_review.v1' or
                review.get('target')!='configured-diagnostic-candidate-r58' or
                review.get('app_sha256')!=app_hash or review.get('app_bytes')!=app_bytes or
                review.get('app_offset')!=0x10000 or review.get('app_slot_bytes')!=0x140000 or
                review.get('predecessor_sha256')!=
                    '7d8ac14ae59272368fbf3031ebc3ad5a5835e84913d85ee5758df46670767b68' or
                review.get('fixed_target_goals')!=[2413,1701] or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Reviewed r58 candidate evidence differs')
    elif revision == 57:
        review,review_sha=_read(root/'runs/wizard-exports',review_id,
                                'attachment-r57-park-return-review.json')
        if (review.get('schema')!='rocell.r57_park_return_review.v1' or
                review.get('target')!='configured-diagnostic-candidate-r57' or
                review.get('app_sha256')!=app_hash or review.get('app_bytes')!=app_bytes or
                review.get('app_offset')!=0x10000 or review.get('app_slot_bytes')!=0x140000 or
                review.get('predecessor_sha256')!=
                    '09864d144d630b2655c78956b0ea8148b0525bcdef017caa843d74f1f4661e79' or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Reviewed r57 candidate evidence differs')
    elif revision == 56:
        review,review_sha=_read(root/'runs/wizard-exports',review_id,
                                'attachment-r56-park-step-review.json')
        if (review.get('schema')!='rocell.r56_park_step_review.v1' or
                review.get('target')!='configured-diagnostic-candidate-r56' or
                review.get('app_sha256')!=app_hash or review.get('app_bytes')!=app_bytes or
                review.get('app_offset')!=0x10000 or review.get('app_slot_bytes')!=0x140000 or
                review.get('predecessor_sha256')!=
                    '1ea884af0cd717775c67046302ab5e9df82b9514b552b96fc8d27d5ad853d9a5' or
                review.get('settings_preserved_by_design') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Reviewed r56 candidate evidence differs')
    elif revision == 55:
        review,review_sha=_read(root/'runs/wizard-exports',review_id,
                                'attachment-r55-park-step-review.json')
        if (review.get('schema')!='rocell.r55_park_step_review.v1' or
                review.get('target')!='configured-diagnostic-candidate-r55' or
                review.get('app_sha256')!=app_hash or review.get('app_bytes')!=app_bytes or
                review.get('app_offset')!=0x10000 or review.get('app_slot_bytes')!=0x140000 or
                review.get('reanchor_route_disabled') is not True or
                review.get('park_step_route_enabled') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Reviewed r55 candidate evidence differs')
    elif revision == 54:
        review,review_sha=_read(root/'runs/wizard-exports',review_id,
                                'attachment-r54-fixed-reanchor-review.json')
        if (review.get('schema')!='rocell.r54_fixed_reanchor_review.v1' or
                review.get('target')!='configured-diagnostic-candidate-r54' or
                review.get('app_sha256')!=app_hash or review.get('app_bytes')!=app_bytes or
                review.get('app_offset')!=0x10000 or review.get('app_slot_bytes')!=0x140000 or
                review.get('recovery_artifacts_verified') is not True or
                review.get('hardware_access') is not False or
                review.get('firmware_uploaded') is not False):
            raise ValueError('Reviewed r54 candidate evidence differs')
    else:
        review,review_sha=_read(root/'runs/wizard-exports',review_id,'attachment-pair-candidate-review.json')
        if (review.get('target')!=f'configured-diagnostic-candidate-r{revision}'
                or review.get('app_offset')!=0x10000 or review.get('app_slot_bytes')!=0x140000
                or review.get('artifacts',{}).get('RoArm-M3_example.ino.bin')!=dict(sha256=app_hash,bytes=app_bytes)
                or review.get('original_backups_match') is not True
                or review.get('original_recovery_matches_backup') is not True
                or review.get('retained_r7_artifact_verified') is not True):
            raise ValueError('Reviewed r10 candidate evidence differs')
    return dict(schema='rocell.held_pair_installation_evidence.v1',
        app_sha256=app_hash,app_bytes=app_bytes,controller_mac=rows[1]['mac'],
        journal_name=journal_name,journal_sha256=hashlib.sha256(raw).hexdigest(),
        candidate_review_export_id=review_id,candidate_review_sha256=review_sha,
        host_reported_flash_readback_verified=True,protected_regions_unchanged=True,
        startup_reset_count=1,application_health_verified=False,
        current_device_bytes_verified=False,pair_configuration_verified=False,
        hardware_access=False,motion_authorized=False)


def export_pair_installation_review(software_root, export_root, *, revision=10):
    report=review_pair_installation(software_root, revision=revision)
    exporter=WizardDiagnosticExporter(Path(export_root));exporter.prepare(create=True)
    saved=exporter.export({'mode':'held-pair-installation-evidence'},[],
        attachments={'held-pair-installation-evidence.json':canonical(report)})
    retained,_=_read(Path(export_root),Path(saved['path']).name,'attachment-held-pair-installation-evidence.json')
    # Re-read authoritative journal and source after export, not just the copy.
    if canonical(retained)!=canonical(report) or canonical(review_pair_installation(software_root, revision=revision))!=canonical(report):
        raise ValueError('Installation evidence changed during export')
    return dict(export_path=saved['path'],report=report)

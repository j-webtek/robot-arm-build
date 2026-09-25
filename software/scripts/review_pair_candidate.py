"""Offline pinned candidate/recovery review. No serial, network or deployment."""
import argparse
import hashlib
import re
import subprocess
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def sha(raw):return hashlib.sha256(raw).hexdigest()


def stack_frames(disassembly):
    # Optimized $isra clones can remain mangled even with objdump -C.
    wanted=('RocellPreparePair','ControllerPairConfigParser','ControllerHoldConfigParser',
            'ConfiguredHeldPairRuntime','HeldPairNetworkLifecycle','HeldPairAuthenticatedRuntime',
            'ElbowConfigurationRoutes','ElbowConfigurationSnapshot','elbow_configuration_json',
            'ElbowGainRoutes','ElbowGainSnapshot','elbow_gain_json',
            'RocellPrepareRecovery','ConfiguredRecoveryRoutes','HoldAuthenticatedRuntime',
            'HoldInitializationOwner','ConfiguredHoldRuntime','AllocatedHoldRuntime','recovery_policy_json',
            'PoseObservation','pose_observation_record','rocellReservePose','registerPoseObservationRoutes',
            'ShoulderConfigurationRoutes','ShoulderConfigurationSnapshot','shoulder_configuration_json',
            'ShoulderSession','ShoulderAuthorizedStart','ShoulderPreload','ShoulderReceipt',
            'shoulder_event_json','rocellPrepareShoulder','registerShoulderSessionRoutes','pollShoulderSession',
            'ShoulderFaultSettling','RocellSettlingAccess','LocalShoulderStep',
            'rocellPrepareLocalStep','rocellLocalMemoryFits','CompensatedShoulder',
            'rocellPrepareCompensatedStep','rocellCompensatedMemoryFits',
            'Characterization','ShoulderCharacterization')
    frames=[];current=None
    for line in disassembly.splitlines():
        match=re.match(r'^[0-9a-f]+ <(.+)>:$',line)
        if match:current=match.group(1)
        entry=re.search(r'\bentry\s+a1,\s*(0x[0-9a-f]+|[0-9]+)',line)
        if entry and current and any(name in current for name in wanted):
            frames.append(dict(symbol=current,frame_bytes=int(entry.group(1),0)));current=None
    return frames


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('compile_export_id')
    parser.add_argument('--revision',type=int,choices=(9,10,11,12,13,14,16,17,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53),default=9)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    report,compile_hash=_read(exports,args.compile_export_id,'attachment-compile-review.json')
    target=f'configured-diagnostic-candidate-r{args.revision}'
    if (report['status']!='COMPILED' or report['target']!=target or
            report['build_profile']!='default-4mb-no-psram' or report['firmware_uploaded'] is not False):
        raise ValueError('Successful offline selected-candidate compile required')
    tools=root/'.firmware-tools';sketch=tools/target/'RoArm-M3_example'
    build=tools/('build-'+target+'--default-4mb-no-psram')
    artifacts={}
    for name,expected in report['artifact_hashes'].items():
        if Path(name).name!=name:raise ValueError('Unsafe artifact path')
        raw=(build/name).read_bytes()
        if sha(raw)!=expected:raise ValueError('Artifact changed after compile')
        artifacts[name]=dict(sha256=expected,bytes=len(raw))
    for path in sketch.iterdir():
        if path.suffix not in ('.h','.ino'):continue
        if sha(path.read_bytes())!=report['source_hashes'][str(path.relative_to(root))]:
            raise ValueError('Candidate source changed after compile')
    prefix='RoArm-M3_example.ino'
    app=artifacts[prefix+'.bin']
    expected_apps={
        53:'8d5ed3f0feb491e2294bb6f56bf27f82c53f616d257c61f493df58d94f050de5',
        52:'0389e22b97cb9e87a97dc4491746af385d3dfcf76c00daaaab434a36b088738b',
        51:'0a45c55ace66374038c712672bee41b507a80e64a121b0a020b4836ce2bddc9e',
        50:'0dda0988222a1de534a5d72de1f528f6ae42fed5be0215fed8fbd75129e6121b',
        49:'e4b331623527aa94078e514f8cd37e18ac00a04bf543b9005072ff677a42c21f',
        48:'e76470e40216c39dd6ebc57df3e665c50fa6436da680bbeea0b18c599deddc1b',
        47:'a2101ea8ec27b7f9c93063b3e5dea91546b91b2edfbca63b3cc5e71f3f7cee1e',
        46:'1b205cffb023761f228be728a8caee9de0e13b17751d4bec28b6ba5584c83d87',
        45:'3b9e5930b9818ee4c4425541f6100d8dc22320eadd883f9d4391ff8499487af6',
        44:'f1910697b4653c941974e9dc9939357ccfe7a7016c526285465decdea2614d7d',
        43:'459e1f31ac103c634b2205654501693d9116bded2bcd9ac1bf8de5284a20fb1b',
        42:'6d3405b3b42db9347ec02445b0937886ca0fba82bf38d905e3989ad48c8f71ea',
        41:'caa26535377b8f35e3bfdc8d0546c779db052a520a355eaab455dcf64defc5cf',
        40:'0bdfad949388b758fff3b8b177a24c9da87e7089ed6a952c6a03b6daf9833213',
        39:'590a2f942214e9830fdfda9ad9610cf4c71c9fec818aa3dacabc02a6291f1156',
        38:'eee1b0f9b8b835573e0237f830108e2f4ead3f88efc3a11651401c7130f0d92e',
        37:'24a3f58df32b5c3db77a6952ed22bf1eddc79c535760afc90abcc67d8e8806ee',
        9:'2af941a662a36f711f9571e34c3ab48b44bb0c2247bab797381c1814e75d3da9',
        10:'b07fd9a442bfeb58a9b846828a5b6cedf25441fd9ce322be9f8f72f32ef9389d',
        11:'52979050aa4fabbe167f01fc1bb7b656105cb370d54f3dd9890c5f6703682b52',
        12:'81227435b8d6b3e36da8e43cd06e88b7d5872e6fc6566eb8d0a5b9a69d7da41d',
        13:'4503aaa00409624ebc0a54876c45eec5af684a6717327046d34a5e7c644b9a6e',
        14:'83ad71a221168ae59c65fc711f781ba6532a996b9b9d28464647ca19e0441281',
        16:'dc8b6f0016d29495ef6403d6a04adcbc192ec45ccd1ede7c390c3d1b4b3ea05e',
        17:'0ed01a2294b19047d95aeeeaf48af6c12d5610128cebe0bd94ca4119ccd5715b',
        19:'18d5586456f4d3552b88edcd3770c6c97677aacfce66eb6dcc33cd2b2914f8ce',
        20:'188e7a96ef11e516655f2f8b9e3efeecb4947a501bdc1ae2beda5cffb5da9572',
        21:'035922452587280362fc1e6fe0120f274647eeb2b0f8ee3c7bc88cb8c3289051',
        22:'047beb3ac792a2c5f85c2b10138d0ca9bd47ae80359af7312138e56f0d132679',
        23:'9edf6bbcf1052a8191d7ecac37195867bb8fafd0149bcaecf585834c807f579b',
        24:'fe3eaec72bb31f72210bec45912b8d5bb4df27adcb292a94decf15106a9436be',
        25:'483604c16de0b2061335873fdc176b90551e16e7552fcd2aa6058e6449bbde5f',
        26:'2a17bdf5a24cb1a3032d0212ca3c2db11d1f6a5b2027fdaf45b44f9c5e4f3c78',
        27:'c46e1ab78cb6b38c1244f1da8dd8b459340704b65af093c3b1875ed3d6158bba',
        28:'88ccd20ebb1607a130cc25f6c5026690cd258cb14ba0d1b0bd763f32540f232e',
        29:'d9d61fc6bcc3b32b6e84a6d3065dcd6bbbf96d374243b83fb140c9e5395baa00',
        30:'e325a0a3062127417bfd23351cf981f7486d79d24e4e9dc53e43ef64732b566c',
        31:'e8400d1c302a70bed3283c4102fa6b202785c1ea35826de2e98754a09b80fae3',
        32:'98e33a9f7ba0e5f5036a0098ef342cadbbfba786496653f2f5b728b9347dca14',
        33:'170188fe380cc7a21ee5502e831f21c3050b34768bdbbbbc1ddf7f7e608b330d',
        36:'1e8564d204aa773149ad54fc58fd70bee294bdfdea74e8d29b2f07de19417dfd',
        35:'c34ebe285db2e31be5c0f4ed35497cd13c280c82a130ac690e120c23f94cda91',
        34:'6637e0e6f06b731db23621d8a727cdc0f9b82a2473813eec9a3b8a98fbd09945',
    }
    if app['sha256']!=expected_apps[args.revision]:
        raise ValueError('Unexpected selected-candidate app identity')
    if not 0<app['bytes']<=0x140000:raise ValueError('Application slot overflow')
    if artifacts[prefix+'.partitions.bin']['sha256']!='148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1':
        raise ValueError('Partition profile mismatch')
    if artifacts[prefix+'.bootloader.bin']['sha256']!='b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7':
        raise ValueError('Bootloader profile mismatch')
    private=root/'private-backups/controller-20260918-session1'
    expected_backup='d9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9'
    backup=(private/'flash-pair-a.bin').read_bytes()
    second=(private/'flash-pair-b.bin').read_bytes()
    recovery=(private/'original-app0-slot.bin').read_bytes()
    if len(backup)!=0x400000 or sha(backup)!=expected_backup or second!=backup:
        raise ValueError('Original backup pair changed')
    if len(recovery)!=0x140000 or recovery!=backup[0x10000:0x150000]:
        raise ValueError('Original recovery application differs from backup')
    r7=tools/'build-configured-diagnostic-candidate-r7--default-4mb-no-psram'/ (prefix+'.bin')
    if sha(r7.read_bytes())!='380d7a69e0b456b25b4ae50e34f8d947724ca5c22db42d75958df509e2618c33':
        raise ValueError('Retained r7 rollback artifact changed')
    boot=(sketch/'diagnostic_boot.h').read_text()
    polling='poll_hold_pair_recovery_diagnostics' if args.revision in (16,17,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53) else 'poll_hold_pair_diagnostics'
    if ('LittleFS.begin(false)' not in boot or polling not in boot or
            any(name in boot for name in ('initHttpWebServer','jsonCmdReceiveHandler','RoArmM3_init'))):
        raise ValueError('Diagnostic entry-point wiring differs')
    elf=build/(prefix+'.elf');elf_hash=sha(elf.read_bytes())
    objdump=tools/'data/packages/esp32/tools/esp-x32/2302/bin/xtensa-esp32-elf-objdump.exe'
    disassembly=subprocess.run([str(objdump),'-d','-C',str(elf)],capture_output=True,text=True,check=True,timeout=60).stdout
    frames=stack_frames(disassembly)
    if not frames:raise ValueError('No relevant compiled frame evidence')
    if args.revision in (33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53):
        board=(sketch/'shoulder_board_session.h').read_text()
        if not board.startswith('#define ROCELL_CHARACTERIZATION_SMOKE 1\n'):
            raise ValueError('Smoke build selection absent')
        registration=(sketch/'configured_pair_board_routes.h').read_text().split('void registerDiagnosticRoutes(){',1)[1]
        if registration.index('registerHoldDiagnosticRoutes();')>registration.index('registerShoulderSessionRoutes();'):
            raise ValueError('Boot identity registration order invalid')
        binary=(build/(prefix+'.bin')).read_bytes()
        for required in (b'/rocell/characterization/prepare',b'/rocell/characterization/start',
                         b'/rocell/characterization/recovery-read',b'RCCRECOVERYRESPONSE01'):
            if required not in binary:raise ValueError('Smoke compiled route/identity absent')
        for forbidden in (b'/rocell/local-step/authorize',b'/rocell/shoulder-session/start'):
            if forbidden in binary:raise ValueError('Competing shoulder route remains exposed')
        if not any('Characterization' in f['symbol'] for f in frames):
            raise ValueError('Campaign frame evidence missing')
        if args.revision in (34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53) and b'/rocell/characterization/reference' not in binary:
            raise ValueError('Reference export route absent')
    if args.revision in (35,36):
        if 'CharacterizationPattern::Matched' not in (sketch/'characterization_smoke_board.h').read_text():
            raise ValueError('Matched selection missing')
        if b'CAMPAIGN_TARGET_EXCURSION' not in binary:
            raise ValueError('Total excursion guard absent')
    if args.revision == 36:
        owner=(sketch/'shoulder_characterization_owner.h').read_text()
        if 'pose.finished_us-sent_<2000000' not in owner or 'CharacterizationOutcome::Stop?3:' not in owner:
            raise ValueError('Response diagnostic policy absent')
    if args.revision == 37:
        owner=(sketch/'shoulder_characterization_owner.h').read_text()
        if 'CharacterizationPattern::Matrix' not in (sketch/'characterization_smoke_board.h').read_text():
            raise ValueError('Matrix selection missing')
        for required in ('consecutive_small_==0', 'CharacterizationOutcome::SettledSmall?4',
                         'pose.finished_us-(matrix_?samples_[0].started_us:sent_)<2000000',
                         'MATRIX_ANCHOR_CHANGED'):
            if required not in owner:raise ValueError('Matrix response policy absent')
        for required in (b'CAMPAIGN_TARGET_EXCURSION', b'MATRIX_ANCHOR_CHANGED',
                         b'SMALL_RESPONSE_RETAINED'):
            if required not in binary:raise ValueError('Compiled matrix guard absent')
    if args.revision == 38:
        pass  # Frozen r38 checks below remain revision-specific.
    if args.revision in (39,40):
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r38/RoArm-M3_example'
        old={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
        new={p.name:p.read_bytes() for p in sketch.iterdir() if p.is_file()}
        expected_changes={'characterization_prepare.h','characterization_controller.h',
                          'shoulder_characterization_owner.h','characterization_smoke_board.h'}
        if old.keys()!=new.keys() or {n for n in old if old[n]!=new[n]}!=expected_changes:
            raise ValueError('Unexpected pilot source change set')
        if new['characterization_smoke_board.h']!=old['characterization_smoke_board.h'].replace(
                b'CharacterizationPattern::Repeatability',
                b'CharacterizationPattern::ABControl' if args.revision==39 else b'CharacterizationPattern::ABCandidate'):
            raise ValueError('Fixed control selector differs')
        if args.revision==40:
            control=root/'.firmware-tools/configured-diagnostic-candidate-r39/RoArm-M3_example'
            control_files={p.name:p.read_bytes() for p in control.iterdir() if p.is_file()}
            if control_files.keys()!=new.keys() or {n for n in new if new[n]!=control_files[n]}!={'characterization_smoke_board.h'}:
                raise ValueError('Candidate changed more than the fixed selector')
        prepare=new['characterization_prepare.h'].decode()
        owner=new['shoulder_characterization_owner.h'].decode()
        for required in ('ab?3:', 'n==0?2377:n==1?2389:pattern==CharacterizationPattern::ABControl?2387:2378',
                         'std::abs(int(current.position[1])-2391)>1'):
            if required not in prepare:raise ValueError('Pilot preparation guard absent')
        for required in ('ab_&&leg_==2', 'p.goal[1]!=2389', 'p.goal[2]!=1725'):
            if required not in owner:raise ValueError('Native matched-start gate absent')
        for required in (b'CAMPAIGN_TARGET_EXCURSION',b'BASELINE_ADMISSION'):
            if required not in binary:raise ValueError('Compiled pilot guard absent')
    if args.revision==41:
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r40/RoArm-M3_example'
        old={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
        new={p.name:p.read_bytes() for p in sketch.iterdir() if p.is_file()}
        changes={'characterization_prepare.h','characterization_controller.h',
                 'shoulder_characterization_owner.h','characterization_smoke_board.h'}
        if old.keys()!=new.keys() or {n for n in old if old[n]!=new[n]}!=changes:
            raise ValueError('Unexpected next-validation source change set')
        if new['characterization_smoke_board.h']!=old['characterization_smoke_board.h'].replace(
                b'CharacterizationPattern::ABCandidate',b'CharacterizationPattern::ForwardRepeat'):
            raise ValueError('Fixed forward-repeat selector differs')
        prepare=new['characterization_prepare.h'].decode();owner=new['shoulder_characterization_owner.h'].decode()
        for required in ('repeat?4:', 'const int primary[4]={2389,2377,2389,2378}',
                         'current.goal[1]!=2378', 'std::abs(int(current.position[1])-2387)>1'):
            if required not in prepare:raise ValueError('Forward-repeat preparation guard absent')
        for required in ('forward_repeat_&&leg_==3','p.goal[1]!=2389','p.goal[2]!=1725'):
            if required not in owner:raise ValueError('Forward-repeat trial gate absent')
        for required in (b'CAMPAIGN_TARGET_EXCURSION',b'BASELINE_ADMISSION'):
            if required not in binary:raise ValueError('Compiled repeat guard absent')
    if args.revision==42:
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r40/RoArm-M3_example'
        old={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
        new={p.name:p.read_bytes() for p in sketch.iterdir() if p.is_file()}
        changes={'characterization_prepare.h','characterization_controller.h',
                 'shoulder_characterization_owner.h','characterization_smoke_board.h'}
        if old.keys()!=new.keys() or {n for n in old if old[n]!=new[n]}!=changes:
            raise ValueError('Unexpected reverse-candidate source change set')
        if new['characterization_smoke_board.h']!=old['characterization_smoke_board.h'].replace(
                b'CharacterizationPattern::ABCandidate',b'CharacterizationPattern::ReverseCandidate'):
            raise ValueError('Fixed reverse-candidate selector differs')
        prepare=new['characterization_prepare.h'].decode();owner=new['shoulder_characterization_owner.h'].decode()
        for required in ('(ab||reverse)?3:',
                         'pattern==CharacterizationPattern::ReverseCandidate?2385:2386',
                         'current.goal[1]!=2378',
                         'std::abs(int(current.position[1])-2387)>1'):
            if required not in prepare:raise ValueError('Reverse-candidate preparation guard absent')
        for required in ('reverse_&&leg_==2','p.goal[1]!=2377','p.goal[2]!=1737',
                         'std::abs(int(p.position[1])-2385)>1'):
            if required not in owner:raise ValueError('Reverse trial gate absent')
        for required in (b'CAMPAIGN_TARGET_EXCURSION',b'BASELINE_ADMISSION'):
            if required not in binary:raise ValueError('Compiled reverse guard absent')
    if args.revision==43:
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r40/RoArm-M3_example'
        old={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
        new={p.name:p.read_bytes() for p in sketch.iterdir() if p.is_file()}
        changes={'characterization_prepare.h','characterization_controller.h',
                 'shoulder_characterization_owner.h','characterization_smoke_board.h'}
        if old.keys()!=new.keys() or {n for n in old if old[n]!=new[n]}!=changes:
            raise ValueError('Unexpected reverse-control source change set')
        if new['characterization_smoke_board.h']!=old['characterization_smoke_board.h'].replace(
                b'CharacterizationPattern::ABCandidate',b'CharacterizationPattern::ReverseControl'):
            raise ValueError('Fixed reverse-control selector differs')
        prepare=new['characterization_prepare.h'].decode();owner=new['shoulder_characterization_owner.h'].decode()
        for required in ('(ab||reverse)?3:',
                         'pattern==CharacterizationPattern::ReverseCandidate?2385:2386',
                         'current.goal[1]!=2385',
                         'std::abs(int(current.position[1])-2387)>2'):
            if required not in prepare:raise ValueError('Reverse-control preparation guard absent')
        for required in ('reverse_&&leg_==2','p.goal[1]!=2377','p.goal[2]!=1737',
                         'std::abs(int(p.position[1])-2385)>1'):
            if required not in owner:raise ValueError('Reverse trial gate absent')
        for required in (b'CAMPAIGN_TARGET_EXCURSION',b'BASELINE_ADMISSION'):
            if required not in binary:raise ValueError('Compiled reverse guard absent')
    if args.revision in (44,45):
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r40/RoArm-M3_example'
        old={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
        new={p.name:p.read_bytes() for p in sketch.iterdir() if p.is_file()}
        changes={'characterization_prepare.h','characterization_controller.h',
                 'shoulder_characterization_owner.h','characterization_smoke_board.h'}
        if old.keys()!=new.keys() or {n for n in old if old[n]!=new[n]}!=changes:
            raise ValueError('Unexpected held-out source change set')
        selector=b'HeldoutCandidate' if args.revision==44 else b'HeldoutControl'
        if new['characterization_smoke_board.h']!=old['characterization_smoke_board.h'].replace(
                b'CharacterizationPattern::ABCandidate',b'CharacterizationPattern::'+selector):
            raise ValueError('Fixed held-out selector differs')
        prepare=new['characterization_prepare.h'].decode();owner=new['shoulder_characterization_owner.h'].decode()
        for required in ('heldout?2:', 'pattern==CharacterizationPattern::HeldoutCandidate?2388:2389',
                         'const bool heldout=', 'current.goal[1]!=2386' if args.revision==44 else 'current.goal[1]!=2388'):
            if required not in prepare:raise ValueError('Held-out preparation guard absent')
        for required in ('heldout_&&leg_==1','p.goal[1]!=2377','p.goal[2]!=1737',
                         'std::abs(int(p.position[1])-2385)>1'):
            if required not in owner:raise ValueError('Held-out trial gate absent')
        for required in (b'CAMPAIGN_TARGET_EXCURSION',b'BASELINE_ADMISSION'):
            if required not in binary:raise ValueError('Compiled held-out guard absent')
    if args.revision in (46,47):
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r40/RoArm-M3_example'
        old={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
        new={p.name:p.read_bytes() for p in sketch.iterdir() if p.is_file()}
        changes={'characterization_prepare.h','characterization_controller.h',
                 'shoulder_characterization_owner.h','characterization_smoke_board.h'}
        if old.keys()!=new.keys() or {n for n in old if old[n]!=new[n]}!=changes:
            raise ValueError('Unexpected second held-out source change set')
        selector=b'SecondHeldoutCandidate' if args.revision==46 else b'SecondHeldoutControl'
        if new['characterization_smoke_board.h']!=old['characterization_smoke_board.h'].replace(
                b'CharacterizationPattern::ABCandidate',b'CharacterizationPattern::'+selector):
            raise ValueError('Fixed second held-out selector differs')
        prepare=new['characterization_prepare.h'].decode();owner=new['shoulder_characterization_owner.h'].decode()
        for required in ('const bool second_heldout=',
                         'SecondHeldoutCandidate?3:4',
                         'n==0?2377:n==1?2389:2378' if args.revision==46 else
                         'n==0?2389:n==1?2377:n==2?2389:2386',
                         'current.goal[1]!=2389' if args.revision==46 else 'current.goal[1]!=2378'):
            if required not in prepare:raise ValueError('Second held-out preparation guard absent')
        for required in ('second_heldout_&&leg_==manifest_.legs-1',
                         'p.goal[1]!=2389','p.goal[2]!=1725',
                         'std::abs(int(p.position[1])-2391)>1'):
            if required not in owner:raise ValueError('Second held-out trial gate absent')
        for required in (b'CAMPAIGN_TARGET_EXCURSION',b'BASELINE_ADMISSION'):
            if required not in binary:raise ValueError('Compiled second held-out guard absent')
    if args.revision==48:
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r47/RoArm-M3_example'
        old={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
        new={p.name:p.read_bytes() for p in sketch.iterdir() if p.is_file()}
        changes={'characterization_prepare.h','characterization_controller.h',
                 'shoulder_characterization_owner.h','characterization_smoke_board.h'}
        if old.keys()!=new.keys() or {n for n in old if old[n]!=new[n]}!=changes:
            raise ValueError('Unexpected mapping-batch source change set')
        if new['characterization_smoke_board.h']!=old['characterization_smoke_board.h'].replace(
                b'CharacterizationPattern::SecondHeldoutControl',
                b'CharacterizationPattern::MappingBatch'):
            raise ValueError('Fixed mapping-batch selector differs')
        prepare=new['characterization_prepare.h'].decode();owner=new['shoulder_characterization_owner.h'].decode()
        for required in ('const bool mapping_batch=',
                         'current.goal[1]!=2386','std::abs(int(current.position[1])-2391)>1',
                         'const int primary[12]={2377,2389,2379,2387,2381,2389,2377,2385,2389,2383,2377,2388}'):
            if required not in prepare:raise ValueError('Mapping-batch preparation guard absent')
        for required in ('mapping_batch_=manifest.legs==12',
                         'const int mapping[12]={2377,2389,2379,2387,2381,2389,2377,2385,2389,2383,2377,2388}',
                         '(matrix_||mapping_batch_)','consecutive_small_==0'):
            if required not in owner:raise ValueError('Mapping-batch outcome policy absent')
        for required in (b'CAMPAIGN_TARGET_EXCURSION',b'SMALL_RESPONSE_RETAINED',
                         b'MEASUREMENTS_COMPLETE'):
            if required not in binary:raise ValueError('Compiled mapping guard absent')
    if args.revision==49:
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r48/RoArm-M3_example'
        old={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
        new={p.name:p.read_bytes() for p in sketch.iterdir() if p.is_file()}
        changes={'characterization_prepare.h','characterization_controller.h',
                 'shoulder_characterization_owner.h','characterization_smoke_board.h'}
        if old.keys()!=new.keys() or {n for n in old if old[n]!=new[n]}!=changes:
            raise ValueError('Unexpected separated-mapping source change set')
        if new['characterization_smoke_board.h']!=old['characterization_smoke_board.h'].replace(
                b'CharacterizationPattern::MappingBatch',
                b'CharacterizationPattern::SeparatedMappingBatch'):
            raise ValueError('Fixed separated-mapping selector differs')
        prepare=new['characterization_prepare.h'].decode();owner=new['shoulder_characterization_owner.h'].decode()
        for required in ('const bool separated_mapping=',
                         'current.goal[1]!=2381','std::abs(int(current.position[1])-2387)>1',
                         'const int primary[12]={2389,2377,2385,2389,2383,2377,2388,2377,2381,2389,2377,2387}'):
            if required not in prepare:raise ValueError('Separated-mapping preparation guard absent')
        for required in ('const int separated[12]={2389,2377,2385,2389,2383,2377,2388,2377,2381,2389,2377,2387}',
                         'separated_mapping=manifest.legs==12',
                         '(matrix_||mapping_batch_)','consecutive_small_==0'):
            if required not in owner:raise ValueError('Separated-mapping outcome policy absent')
        for required in (b'CAMPAIGN_TARGET_EXCURSION',b'SMALL_RESPONSE_RETAINED',
                         b'MEASUREMENTS_COMPLETE'):
            if required not in binary:raise ValueError('Compiled separated-mapping guard absent')
    if args.revision==50:
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r49/RoArm-M3_example'
        old={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
        new={p.name:p.read_bytes() for p in sketch.iterdir() if p.is_file()}
        changes={'characterization_prepare.h','characterization_controller.h',
                 'shoulder_characterization_owner.h','characterization_smoke_board.h'}
        if old.keys()!=new.keys() or {n for n in old if old[n]!=new[n]}!=changes:
            raise ValueError('Unexpected fine-lookup source change set')
        if new['characterization_smoke_board.h']!=old['characterization_smoke_board.h'].replace(
                b'CharacterizationPattern::SeparatedMappingBatch',
                b'CharacterizationPattern::FineLookupValidation'):
            raise ValueError('Fixed fine-lookup selector differs')
        prepare=new['characterization_prepare.h'].decode();owner=new['shoulder_characterization_owner.h'].decode()
        for required in ('const bool fine_lookup=',
                         'current.goal[1]!=2387','std::abs(int(current.position[1])-2389)>1',
                         'const int primary[12]={2377,2385,2389,2377,2385,2389,2377,2388,2389,2377,2388,2389}'):
            if required not in prepare:raise ValueError('Fine-lookup preparation guard absent')
        for required in ('const int fine_lookup[12]={2377,2385,2389,2377,2385,2389,2377,2388,2389,2377,2388,2389}',
                         'fine_lookup_validation=manifest.legs==12',
                         '(matrix_||mapping_batch_)','consecutive_small_==0'):
            if required not in owner:raise ValueError('Fine-lookup outcome policy absent')
        for required in (b'CAMPAIGN_TARGET_EXCURSION',b'SMALL_RESPONSE_RETAINED',
                         b'MEASUREMENTS_COMPLETE'):
            if required not in binary:raise ValueError('Compiled fine-lookup guard absent')
    if args.revision==51:
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r50/RoArm-M3_example'
        old={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
        new={p.name:p.read_bytes() for p in sketch.iterdir() if p.is_file()}
        changes={'characterization_prepare.h','characterization_controller.h',
                 'shoulder_characterization_owner.h','characterization_smoke_board.h'}
        if old.keys()!=new.keys() or {n for n in old if old[n]!=new[n]}!=changes:
            raise ValueError('Unexpected local-interval source change set')
        if new['characterization_smoke_board.h']!=old['characterization_smoke_board.h'].replace(
                b'CharacterizationPattern::FineLookupValidation',
                b'CharacterizationPattern::LocalIntervalCampaign'):
            raise ValueError('Fixed local-interval selector differs')
        prepare=new['characterization_prepare.h'].decode();owner=new['shoulder_characterization_owner.h'].decode()
        for required in ('const bool local_interval=',
                         'current.goal[1]!=2389','std::abs(int(current.position[1])-2391)>1',
                         'const int primary[11]={2377,2383,2389,2377,2385,2389,2377,2388,2389,2377,2389}'):
            if required not in prepare:raise ValueError('Local-interval preparation guard absent')
        for required in ('const int local_interval[11]={2377,2383,2389,2377,2385,2389,2377,2388,2389,2377,2389}',
                         'local_interval_campaign=manifest.legs==11',
                         '(matrix_||mapping_batch_)','consecutive_small_==0'):
            if required not in owner:raise ValueError('Local-interval outcome policy absent')
        for required in (b'CAMPAIGN_TARGET_EXCURSION',b'SMALL_RESPONSE_RETAINED',
                         b'MEASUREMENTS_COMPLETE'):
            if required not in binary:raise ValueError('Compiled local-interval guard absent')
    if args.revision==52:
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r51/RoArm-M3_example'
        old={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
        new={p.name:p.read_bytes() for p in sketch.iterdir() if p.is_file()}
        changes={'characterization_prepare.h','characterization_controller.h',
                 'shoulder_characterization_owner.h','characterization_smoke_board.h'}
        if old.keys()!=new.keys() or {n for n in old if old[n]!=new[n]}!=changes:
            raise ValueError('Unexpected ghost-transition source change set')
        if new['characterization_smoke_board.h']!=old['characterization_smoke_board.h'].replace(
                b'CharacterizationPattern::LocalIntervalCampaign',
                b'CharacterizationPattern::GhostPairTransitionCampaign'):
            raise ValueError('Fixed ghost-transition selector differs')
        prepare=new['characterization_prepare.h'].decode()
        owner=new['shoulder_characterization_owner.h'].decode()
        for required in ('const bool ghost_transition=',
                         'current.goal[1]!=2389','std::abs(int(current.position[1])-2391)>1',
                         'const int primary[12]={2377,2386,2388,2386,2388,2386,2377,2386,2388,2386,2388,2389}'):
            if required not in prepare:raise ValueError('Ghost-transition preparation guard absent')
        for required in ('const int ghost_pair[12]={2377,2386,2388,2386,2388,2386,2377,2386,2388,2386,2388,2389}',
                         'ghost_pair_transition_=manifest.legs==12',
                         'GHOST_ENDPOINT_OR_DIRECTION','GHOST_SMALL_STREAK',
                         'GHOST_VERIFIED_SMALL_RESPONSE','direct_small_streak_'):
            if required not in owner:raise ValueError('Ghost-transition outcome policy absent')
        for required in (b'GHOST_ENDPOINT_OR_DIRECTION',b'GHOST_SMALL_STREAK',
                         b'GHOST_VERIFIED_SMALL_RESPONSE',b'MEASUREMENTS_COMPLETE'):
            if required not in binary:raise ValueError('Compiled ghost-transition guard absent')
    if args.revision==53:
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r52/RoArm-M3_example'
        old={p.name:p.read_bytes() for p in previous.iterdir() if p.is_file()}
        new={p.name:p.read_bytes() for p in sketch.iterdir() if p.is_file()}
        if (old.keys()!=new.keys() or
                {name for name in old if old[name]!=new[name]}!={'shoulder_characterization_owner.h'}):
            raise ValueError('Unexpected direct-window source change set')
        owner=new['shoulder_characterization_owner.h'].decode()
        if ('if(direct&&result.outcome!=CharacterizationOutcome::Stop&&' not in owner or
                'pose.finished_us-samples_[0].started_us<2000000)return;' not in owner or
                'GHOST_ENDPOINT_OR_DIRECTION' not in owner or
                'GHOST_VERIFIED_SMALL_RESPONSE' not in owner):
            raise ValueError('Direct-window guard or final endpoint policy absent')
        for required in (b'GHOST_ENDPOINT_OR_DIRECTION',b'GHOST_SMALL_STREAK',
                         b'GHOST_VERIFIED_SMALL_RESPONSE',b'MEASUREMENTS_COMPLETE'):
            if required not in binary:raise ValueError('Compiled direct-window guard absent')
    if args.revision == 38:
        board=(sketch/'characterization_smoke_board.h').read_text()
        prepare=(sketch/'characterization_prepare.h').read_text()
        if 'CharacterizationPattern::Repeatability' not in board:
            raise ValueError('Repeatability selection missing')
        if ('const int repeatability[6]={-12,0,-12,0,-12,0}' not in prepare or
                'pattern==CharacterizationPattern::Repeatability?6:12' not in prepare):
            raise ValueError('Exact six-leg preparation absent')
        previous=root/'.firmware-tools/configured-diagnostic-candidate-r37/RoArm-M3_example'
        for name in ('shoulder_characterization_owner.h','shoulder_characterization_policy.h'):
            if (sketch/name).read_bytes()!=(previous/name).read_bytes():
                raise ValueError('Repeatability unexpectedly changed outcome policy')
        if b'CAMPAIGN_TARGET_EXCURSION' not in binary:
            raise ValueError('Compiled excursion guard absent')
    if args.revision == 22 and not any('ShoulderConfiguration' in f['symbol'] for f in frames):
        raise ValueError('Shoulder diagnostic frame evidence missing')
    if args.revision in (23,24,25,26,27,28,29,30):
        for required in ('ShoulderPreloadSession','rocellPrepareShoulder','pollShoulderSession'):
            if not any(required in f['symbol'] for f in frames):
                raise ValueError('Shoulder session compiled frame evidence missing: '+required)
    if args.revision==25:
        board=(sketch/'shoulder_board_session.h').read_text()
        if not board.startswith('#define ROCELL_MIXED_TARGET_EXPERIMENT 1\n'):
            raise ValueError('Mixed experiment build selection absent')
        if b'mixed-shoulder-target-v1' not in (build/(prefix+'.bin')).read_bytes():
            raise ValueError('Mixed command identity absent from binary')
    if args.revision==26:
        board=(sketch/'shoulder_board_session.h').read_text()
        if not board.startswith('#define ROCELL_POSE_PREPARATION 1\n'):
            raise ValueError('Pose preparation build selection absent')
        if b'pose-preparation-v1' not in (build/(prefix+'.bin')).read_bytes():
            raise ValueError('Pose preparation identity absent from binary')
    if args.revision==27:
        board=(sketch/'shoulder_board_session.h').read_text()
        if not board.startswith('#define ROCELL_SHOULDER_RISE 1\n'):
            raise ValueError('Shoulder rise build selection absent')
        if b'shoulder-rise12-v1' not in (build/(prefix+'.bin')).read_bytes():
            raise ValueError('Shoulder rise identity absent from binary')
    if args.revision==28:
        board=(sketch/'shoulder_board_session.h').read_text()
        if not board.startswith('#define ROCELL_CLEARANCE_RECOVERY 1\n'):
            raise ValueError('Clearance recovery build selection absent')
        if b'shoulder-clearance24-v1' not in (build/(prefix+'.bin')).read_bytes():
            raise ValueError('Clearance recovery identity absent from binary')
    if args.revision==29:
        board=(sketch/'shoulder_board_session.h').read_text()
        if not board.startswith('#define ROCELL_STABLE_CLEARANCE_RECOVERY 1\n'):
            raise ValueError('Stable recovery build selection absent')
        if b'shoulder-stable-clearance24-v1' not in (build/(prefix+'.bin')).read_bytes():
            raise ValueError('Stable recovery identity absent from binary')
    if args.revision==30:
        board=(sketch/'shoulder_board_session.h').read_text()
        if not board.startswith('#define ROCELL_STABLE_CLEARANCE_RECOVERY 1\n#define ROCELL_FAULT_SETTLING_CAPTURE 1\n'):
            raise ValueError('Fault settling build selection absent')
        binary=(build/(prefix+'.bin')).read_bytes()
        for required in (b'/rocell/shoulder-settling/status',b'/rocell/shoulder-settling/start',
                         b'/rocell/shoulder-settling/record',b'/rocell/shoulder-settling/receipt',
                         b'FAULT_SETTLING_SAMPLE',b'original_fault_sha256'):
            if required not in binary:raise ValueError('Fault settling compiled identity absent')
        if not any('ShoulderFaultSettling' in f['symbol'] for f in frames):
            raise ValueError('Fault settling frame evidence missing')
    if args.revision==31:
        board=(sketch/'shoulder_board_session.h').read_text()
        if not board.startswith('#define ROCELL_LOCAL_SHOULDER_STEP 1\n'):
            raise ValueError('Local step build selection absent')
        binary=(build/(prefix+'.bin')).read_bytes()
        for required in (b'/rocell/local-step/prepare',b'/rocell/local-step/status',
                         b'/rocell/local-step/authorize',b'/rocell/local-step/record',b'/rocell/local-step/receipt',
                         b'/rocell/shoulder-settling/start',b'reference_sha256',b'rocell.local_shoulder_step.v1'):
            if required not in binary:raise ValueError('Local step compiled identity absent')
        if b'/rocell/shoulder-session/start' in binary:raise ValueError('Legacy movement route remains exposed')
        for required in ('LocalShoulderStepSession','LocalShoulderStepAuthorization','rocellPrepareLocalStep'):
            if not any(required in f['symbol'] for f in frames):raise ValueError('Local step frame evidence missing: '+required)
    if args.revision==32:
        board=(sketch/'shoulder_board_session.h').read_text()
        if not board.startswith('#define ROCELL_COMPENSATED_SHOULDER_STEP 1\n'):
            raise ValueError('Compensated build selection absent')
        binary=(build/(prefix+'.bin')).read_bytes()
        for required in (b'/rocell/compensated-step/prepare',b'/rocell/compensated-step/status',
                         b'/rocell/compensated-step/authorize',b'/rocell/compensated-step/record',
                         b'/rocell/compensated-step/receipt',b'/rocell/shoulder-settling/start',
                         b'rocell.compensated_shoulder_step.v1',b'desired_error_counts',b'goal_residual_counts'):
            if required not in binary:raise ValueError('Compensated identity absent')
        for forbidden in (b'/rocell/shoulder-session/start',b'/rocell/local-step/prepare'):
            if forbidden in binary:raise ValueError('Other movement route remains exposed')
        for required in ('CompensatedShoulderStepSession','CompensatedShoulderAuthorization','rocellPrepareCompensatedStep'):
            if not any(required in f['symbol'] for f in frames):raise ValueError('Compensated frame missing: '+required)
    review=dict(schema='rocell.pair_candidate_review.v1',target=target,
        reviewer_sha256=sha(Path(__file__).read_bytes()),
        compile_export_id=args.compile_export_id,compile_report_sha256=compile_hash,
        artifacts=artifacts,app_offset=0x10000,app_slot_bytes=0x140000,
        app_headroom_bytes=0x140000-app['bytes'],original_backups_match=True,
        original_recovery_matches_backup=True,retained_r7_artifact_verified=True,
        diagnostic_entrypoint_checked=True,elf_sha256=elf_hash,static_frames=frames,
        static_frames_are_total_stack_bound=False,elf_to_app_link_independently_verified=False,
        current_device_bytes_verified=False,runtime_resources_verified=False,
        hardware_access=False,firmware_uploaded=False,provisioning_performed=False,deployable=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-pair-candidate-review'},[],
        attachments={'pair-candidate-review.json':canonical(review)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Review export failed')
    print(canonical(dict(export_path=saved['path'],app_sha256=app['sha256'],
        static_frames=len(frames),largest_individual_frame=max(f['frame_bytes'] for f in frames),
        app_headroom_bytes=review['app_headroom_bytes'],deployable=False)).decode())


if __name__=='__main__':main()

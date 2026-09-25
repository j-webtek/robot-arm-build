"""Freeze one follow-up validation candidate from verified r40. Offline only."""
import argparse
import hashlib
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

VARIANTS={'forward_repeat':(41,'ForwardRepeat'),'reverse_candidate':(42,'ReverseCandidate'),
          'reverse_control':(43,'ReverseControl'),'heldout_candidate':(44,'HeldoutCandidate'),
          'heldout_control':(45,'HeldoutControl'),
          'second_heldout_candidate':(46,'SecondHeldoutCandidate'),
          'second_heldout_control':(47,'SecondHeldoutControl'),
          'mapping_batch':(48,'MappingBatch'),
          'separated_mapping_batch':(49,'SeparatedMappingBatch'),
          'fine_lookup_validation':(50,'FineLookupValidation'),
          'local_interval_campaign':(51,'LocalIntervalCampaign'),
          'ghost_pair_transition_campaign':(52,'GhostPairTransitionCampaign')}
HEADERS=('characterization_prepare.h','characterization_controller.h',
         'shoulder_characterization_owner.h')
PREDECESSOR='wizard-20260920T185347392266Z-f3e2a8433061406d8f5eda3789aa139d'
R47_COMPILE='wizard-20260920T205446973251Z-8976b7d26d31403f9a40f3c8c5818e35'


def stage(root,variant):
    revision,selector=VARIANTS[variant];exports=root/'runs/wizard-exports'
    predecessor_revision=(51 if variant=='ghost_pair_transition_campaign' else
                          50 if variant=='local_interval_campaign' else
                          49 if variant=='fine_lookup_validation' else
                          48 if variant=='separated_mapping_batch' else
                          47 if variant=='mapping_batch' else 40)
    prefix=f'.firmware-tools/configured-diagnostic-candidate-r{predecessor_revision}/RoArm-M3_example/'
    source_compile=('wizard-20260921T030956990516Z-bb60378cb348435a897d1f8b08083b78'
                    if variant=='ghost_pair_transition_campaign' else
                    'wizard-20260921T020149348463Z-cabf450e3bc44b66af61f58e5f77cb6d'
                    if variant=='local_interval_campaign' else
                    'wizard-20260920T220450539161Z-281bba4e5ff94c94a14e4ebfd733d2ef'
                    if variant=='fine_lookup_validation' else
                    'wizard-20260920T213222876827Z-02a4a76763f648af84d117d20565d499'
                    if variant=='separated_mapping_batch' else R47_COMPILE if variant=='mapping_batch' else PREDECESSOR)
    report,receipt=_read(exports,source_compile,
                         'attachment-compile-review.json')
    expected={Path(p).name:h for p,h in report['source_hashes'].items()
              if p.replace('\\','/').startswith(prefix)}
    files={p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    if (report['status']!='COMPILED' or not expected or set(expected)!=set(files) or
        any(sha(raw)!=expected[n] for n,raw in files.items())):
        raise ValueError('Pinned r40 source differs')
    before={n:sha(raw) for n,raw in files.items()}
    for name in HEADERS:files[name]=(root/'firmware/diagnostics'/name).read_bytes()
    board='characterization_smoke_board.h'
    old=(b'CharacterizationPattern::LocalIntervalCampaign' if variant=='ghost_pair_transition_campaign' else
         b'CharacterizationPattern::FineLookupValidation' if variant=='local_interval_campaign' else
         b'CharacterizationPattern::SeparatedMappingBatch' if variant=='fine_lookup_validation' else
         b'CharacterizationPattern::MappingBatch' if variant=='separated_mapping_batch' else
         b'CharacterizationPattern::SecondHeldoutControl' if variant=='mapping_batch'
         else b'CharacterizationPattern::ABCandidate')
    if files[board].count(old)!=1:raise ValueError('Expected one r40 selector')
    files[board]=files[board].replace(old,('CharacterizationPattern::'+selector).encode())
    changes={n:dict(before=before[n],after=sha(raw)) for n,raw in files.items()
             if before[n]!=sha(raw)}
    if set(changes)!=set(HEADERS)|{board}:raise ValueError('Unexpected change set')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    target=root/f'.firmware-tools/configured-diagnostic-candidate-r{revision}/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:stream.write(raw)
        if (target/name).read_bytes()!=raw:raise ValueError('Stage readback differs')
    saved=exporter.export({'mode':'next-validation-stage'},[],attachments={
        'next-validation-stage.json':canonical(dict(revision=revision,variant=variant,
        selector=selector,predecessor_compile_receipt=receipt,changed_files=changes,
        hardware_access=False,uploaded=False,settings_changed=False,deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Stage export failed')
    return saved['path']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant',required=True,choices=VARIANTS);args=parser.parse_args()
    print(stage(Path(__file__).resolve().parents[1],args.variant))

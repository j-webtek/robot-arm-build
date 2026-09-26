"""Apply a predeclared conservative calibration rule to a fresh larger study."""
import argparse,hashlib,json
from pathlib import Path
import sys
AI_DIR=Path(__file__).resolve().parents[1];ROOT=AI_DIR.parents[1]
sys.path[:0]=[str(AI_DIR),str(AI_DIR.parent/'src')]
from vision.evaluate_localization_radius import evaluate
from rocell_ai.scene_observation import canonical_hash


def summarize(study, manifest):
    coverage_pass=study['evaluation_empirical_coverage']>=manifest['minimum_evaluation_coverage']
    fit_pass=len(study['nominal_center_targets_fitting_radius'])>=manifest['minimum_fitting_targets']
    core={k:v for k,v in study.items() if k not in ('schema','calibration_groups','evaluation_groups','study_sha256')}
    core.update(schema='rocell.ai_conservative_radius_study.v0',source_study_sha256=study['study_sha256'],
        minimum_evaluation_coverage=manifest['minimum_evaluation_coverage'],
        minimum_fitting_targets=manifest['minimum_fitting_targets'],
        coverage_criterion_passed=coverage_pass,nominal_fit_criterion_passed=fit_pass,
        status='SYNTHETIC_CRITERIA_PASS_UNQUALIFIED' if coverage_pass and fit_pass else 'SYNTHETIC_CRITERIA_FAILED')
    for split in ('calibration','evaluation'):
        core[split+'_scores']=[{'seed':g['seed'],'maximum_error_mm':g['maximum_error_mm'],
                               'group_sha256':canonical_hash(g)} for g in study[split+'_groups']]
    core['limitations']=[*study['limitations'],
        '99% calibration quantile and 95% evaluation criterion were declared before scoring',
        'Evaluation coverage is descriptive, not a population confidence bound',
        'Passing these study criteria does not install a trusted qualification or validate a deployment domain']
    return {**core,'report_sha256':canonical_hash(core)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--full-output',type=Path)
    args=p.parse_args()
    manifest=json.loads(args.manifest.read_text())
    full=evaluate(args.manifest,args.checkpoint)
    report=summarize(full,manifest)
    if args.full_output:
        args.full_output.parent.mkdir(parents=True,exist_ok=True)
        args.full_output.write_bytes((json.dumps(full,indent=2,sort_keys=True)+'\n').encode())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes((json.dumps(report,indent=2,sort_keys=True)+'\n').encode())
    print(report['status'],'radius',report['empirical_radius_mm'],'coverage',report['evaluation_empirical_coverage'],
          'targets fitting',len(report['nominal_center_targets_fitting_radius']))

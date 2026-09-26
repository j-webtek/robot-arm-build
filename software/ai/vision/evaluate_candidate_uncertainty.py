"""Fresh candidate radius and actual independent target-region fit; research only."""
import hashlib,json,sys
from pathlib import Path
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
from vision.evaluate_localization_radius import evaluate
from vision.evaluate_conservative_radius import summarize
from vision.synthetic_keyboard import catalog_for_workspace,transform_target
from vision.evaluate_prediction_margin import margin
from rocell_ai.scene_observation import canonical_hash


def run():
    path=AI/'eval/candidate_uncertainty_v0.manifest.json'
    manifest=json.loads(path.read_text())
    checkpoint=AI/'results/translation_weighted_v0_translation_weighted/pose_model.pt'
    full=evaluate(path,checkpoint)
    report=summarize(full,manifest)
    catalog=catalog_for_workspace(ROOT);radius=full['empirical_radius_mm']
    fitted=0;total=0;group_fit=0;image_fit=0;details=[]
    for group in full['evaluation_groups']:
        all_group=True;case_counts=[]
        for case in group['cases']:
            truth=case['truth_pose'];pred=case['predicted_pose'];count=0
            for region in catalog.keyboard_targets.values():
                point=transform_target(region.center.x,region.center.y,pred[:2],pred[2])
                center=transform_target(region.center.x,region.center.y,truth[:2],truth[2])
                count+=margin(point,center,truth[2],(region.half_extent_x_mm,region.half_extent_y_mm),radius)>=0
            fitted+=count;total+=len(catalog.keyboard_targets)
            all_case=count==len(catalog.keyboard_targets);image_fit+=all_case;all_group &= all_case
            case_counts.append(dict(condition=case['condition'],fitting_targets=count))
        group_fit+=all_group;details.append(dict(seed=group['seed'],cases=case_counts,all_targets_fit=all_group))
    fraction=group_fit/len(full['evaluation_groups'])
    report.pop('report_sha256');report['radius_study_status']=report.pop('status')
    report.update(actual_oracle_fitting_targets=fitted,total_target_predictions=total,
        actual_oracle_all_targets_fit_images=image_fit,actual_oracle_all_targets_fit_groups=group_fit,
        actual_oracle_group_fit_fraction=fraction,minimum_actual_group_fit_fraction=manifest['minimum_actual_group_fit_fraction'],
        actual_oracle_fit_groups=details,physical_movements=0,
        status='SYNTHETIC_COMBINED_CRITERIA_PASS_UNQUALIFIED' if report['coverage_criterion_passed'] and fraction>=manifest['minimum_actual_group_fit_fraction'] else 'SYNTHETIC_COMBINED_CRITERIA_FAIL')
    report['limitations'].extend(['Actual safe regions use hidden rendered truth for evaluation only, not runtime calibration',
        'Complete disk fit around predicted coordinates differs from ideal-center fit',
        'No confidence model, capture authentication, calibration installation or runtime checkpoint replacement'])
    report['report_sha256']=canonical_hash(report)
    out=AI/'results/candidate_uncertainty_v0_full.json'
    if out.exists(): raise ValueError('preserve prior full evidence')
    out.write_bytes((json.dumps(full,indent=2)+'\n').encode())
    (AI/'eval/candidate_uncertainty_v0_scorecard.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps({k:report[k] for k in ('status','empirical_radius_mm','evaluation_empirical_coverage','actual_oracle_group_fit_fraction','actual_oracle_fitting_targets','total_target_predictions')}))


if __name__=='__main__': run()

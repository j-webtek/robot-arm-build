"""Read-only Cartesian preflight by default; --execute sends one selected Z leg.

The operator must secure the arm and clear the small route. This is noncontact
controller-frame commissioning, not board/tool calibration or task execution.
"""
import argparse
import json
from pathlib import Path
from rocell.application.controller_route_preview import preview_vertical_pair, preview_elbow_isolation
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from rocell.providers.windows.arm_wifi_deadline import bounded_probe
from rocell.providers.windows.arm_transport_lock import arm_transport_lock
from rocell.providers.windows.wifi_cartesian_native import run_native_vertical_trial


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true',help='Physically send one screened Z command; no return or retry')
    parser.add_argument('--local-tip-press',action='store_true',help='One named hypothetical 2 mm tip press; no contact or return')
    parser.add_argument('--post-transfer-tip',action='store_true',help='One coordinated 2 mm virtual press at the verified wrist-cycle posture')
    parser.add_argument('--local-tip-retract',action='store_true',help='Separate uncompensated 2 mm upward diagnostic; no automatic cycle')
    parser.add_argument('--local-tip-candidate',action='store_true',help='Pinned held-out local-tip correction with desired-endpoint verification')
    parser.add_argument('--post-transfer-candidate',action='store_true',help='Pinned current-posture coordinated correction; one held-out trial')
    parser.add_argument('--affine-interior',action='store_true',help='Frozen interior-domain coordinated response trial; not a keypress')
    parser.add_argument('--ghost-first-step',action='store_true',help='Exclusive first 5 mm ghost approach diagnostic')
    parser.add_argument('--ghost-post-wrist',action='store_true',help='Exclusive 5 mm approach from the validated post-wrist posture')
    parser.add_argument('--coordinated-candidate',action='store_true',help='Frozen elbow/wrist correction held-out trial, with desired-endpoint completion')
    parser.add_argument('--coordinated-v2',action='store_true',help='Revised local bias; requires --coordinated-candidate')
    parser.add_argument('--wrist-probe',action='store_true',help='Exclusive post-approach -1.5 degree wrist diagnostic')
    parser.add_argument('--post-tip-wrist',action='store_true',help='Uncompensated current-posture wrist response diagnostic')
    parser.add_argument('--post-overshoot-wrist',action='store_true',help='Separate uncompensated wrist diagnostic at the post-overshoot elbow posture')
    parser.add_argument('--post-overshoot-wrist-candidate',action='store_true',help='Held-out transfer of frozen decreasing wrist correction; no refitting')
    parser.add_argument('--post-tip-wrist-candidate',action='store_true',help='Pinned local wrist correction held-out trial')
    parser.add_argument('--post-tip-wrist-reverse',action='store_true',help='Separate uncompensated increasing wrist diagnostic')
    parser.add_argument('--post-tip-wrist-reverse-candidate',action='store_true',help='Pinned increasing-direction held-out correction')
    parser.add_argument('--wrist-map-trial',choices=('prepare','held-out','transfer'),help='One named interpolation preparation or validation leg')
    parser.add_argument('--wrist-post-coordinated',action='store_true',help='Separate -1.5 degree wrist diagnostic at the latest coordinated posture')
    parser.add_argument('--wrist-ascending',action='store_true',help='Separate +1.5 degree post-coordinated diagnostic; no descending correction')
    parser.add_argument('--wrist-pair-leg',choices=('down','up'),help='One shared-endpoint leg; no automatic next leg')
    parser.add_argument('--wrist-candidate',action='store_true',help='Frozen local wrist correction; requires --wrist-probe')
    parser.add_argument('--wrist-extended-start',action='store_true',help='Separate v2 wrist starting-range experiment')
    parser.add_argument('--wrist-prepare',action='store_true',help='Separate wrist preparation; requires --wrist-probe')
    parser.add_argument('--wrist-clean',action='store_true',help='Finish at verified desired wrist arrival; requires --wrist-candidate')
    parser.add_argument('--wrist-nearby-target',action='store_true',help='Held-out nearby target with unchanged post-coordinated wrist correction')
    parser.add_argument('--step-mm',type=int,choices=(2,5),default=2)
    parser.add_argument('--elbow-only',action='store_true',help='Use fixed -2 degree elbow-only diagnostic instead of Cartesian Z')
    parser.add_argument('--post-tip-elbow',action='store_true',help='Separate elbow-only reverse comparison with explicit 20/1 settings')
    parser.add_argument('--post-tip-elbow-increasing',action='store_true',help='Separate +0.012 rad elbow response diagnostic, not an amplitude escalation')
    parser.add_argument('--post-overshoot-elbow',action='store_true',help='Separate -0.008 rad elbow diagnostic with retained 6 mm observation bound')
    parser.add_argument('--post-overshoot-elbow-speed40',action='store_true',help='Same target at speed 40, acceleration 1; one diagnostic only')
    parser.add_argument('--elbow-degrees',type=int,choices=(2,5,-3),default=2,
                        help='Lift magnitude: 2/5, or -3 for fixed +3-degree reverse comparison; requires --elbow-only')
    parser.add_argument('--elbow-local-validation',action='store_true',help='Fixed experimental ascending correction; not a relative lift')
    parser.add_argument('--extended-candidate-start',action='store_true',help='Separate v2 start-range experiment; requires local validation')
    parser.add_argument('--nearby-candidate-target',action='store_true',help='Separate v3 target 0.01 rad below original; requires local validation')
    parser.add_argument('--descending-candidate',action='store_true',help='Separate decreasing-angle correction; requires local validation')
    parser.add_argument('--revised-descending',action='store_true',help='Use frozen descending v2; requires --descending-candidate')
    parser.add_argument('--mapping-sample',action='store_true',help='Fixed-start identification point; exclusive local validation')
    args=parser.parse_args()
    if args.affine_interior:
        if args.post_transfer_candidate:parser.error('Choose one candidate model')
        args.post_transfer_candidate=True
    if args.post_transfer_candidate:
        if args.local_tip_candidate:parser.error('Choose one tip candidate')
        args.local_tip_candidate=True
    if args.post_transfer_tip:
        if args.local_tip_press:parser.error('Choose one local press posture')
        args.local_tip_press=True
    if args.post_overshoot_wrist_candidate:
        if any((args.post_overshoot_wrist,args.post_tip_wrist_candidate,args.post_tip_wrist_reverse_candidate)):
            parser.error('Choose one candidate scope')
        args.post_tip_wrist_candidate=True
    if args.post_overshoot_wrist:
        if args.post_tip_wrist:parser.error('Choose one wrist posture')
        args.post_tip_wrist=True
    if args.post_overshoot_elbow_speed40:
        if args.post_overshoot_elbow:parser.error('Choose one speed variant')
        args.post_overshoot_elbow=True
    if args.post_overshoot_elbow:
        if args.post_tip_elbow or args.post_tip_elbow_increasing or args.elbow_only or args.elbow_degrees!=2 or args.elbow_local_validation:
            parser.error('Post-overshoot elbow diagnostic is exclusive')
        args.elbow_only=True;args.elbow_degrees=-10 if args.post_overshoot_elbow_speed40 else -9
    if args.post_tip_elbow_increasing:
        if args.post_tip_elbow or args.elbow_only or args.elbow_degrees!=2 or args.elbow_local_validation:
            parser.error('Increasing elbow diagnostic is exclusive')
        args.elbow_only=True;args.elbow_degrees=-8
    if args.wrist_map_trial:
        if any((args.post_tip_wrist,args.post_tip_wrist_reverse,args.post_tip_wrist_candidate,args.post_tip_wrist_reverse_candidate,args.wrist_probe,args.wrist_candidate,args.wrist_prepare,args.wrist_post_coordinated,args.wrist_ascending,args.wrist_pair_leg,args.wrist_clean,args.wrist_extended_start,args.wrist_nearby_target)):
            parser.error('Mapping trial is exclusive')
        args.wrist_probe='map-'+args.wrist_map_trial;args.wrist_candidate=True;args.wrist_clean=True
    if args.post_tip_wrist_reverse_candidate:
        if args.post_tip_wrist_reverse or args.post_tip_wrist_candidate:
            parser.error('Choose one candidate direction')
        args.post_tip_wrist_candidate=True
    if args.post_tip_wrist_reverse:
        if any((args.post_tip_wrist,args.post_tip_wrist_candidate,args.wrist_probe,args.wrist_candidate,args.wrist_prepare,args.wrist_post_coordinated,args.wrist_ascending,args.wrist_pair_leg,args.wrist_clean,args.wrist_extended_start,args.wrist_nearby_target)):
            parser.error('Reverse wrist diagnostic is exclusive')
        args.wrist_probe='post-tip-reverse'
    if args.post_tip_wrist_candidate:
        if any((args.post_tip_wrist,args.wrist_probe,args.wrist_candidate,args.wrist_prepare,args.wrist_post_coordinated,args.wrist_ascending,args.wrist_pair_leg,args.wrist_clean,args.wrist_extended_start,args.wrist_nearby_target)):
            parser.error('Held-out wrist trial is exclusive')
        args.wrist_probe='post-tip-reverse-candidate' if args.post_tip_wrist_reverse_candidate else 'post-tip-candidate'
        if args.post_overshoot_wrist_candidate:args.wrist_probe='post-overshoot-candidate'
        args.wrist_candidate=True;args.wrist_clean=True
    if args.post_tip_wrist:
        if any((args.wrist_probe,args.wrist_candidate,args.wrist_prepare,args.wrist_post_coordinated,args.wrist_ascending,args.wrist_pair_leg,args.wrist_clean,args.wrist_extended_start,args.wrist_nearby_target)):
            parser.error('Post-tip wrist diagnostic is exclusive and uncompensated')
        args.wrist_probe='post-overshoot' if args.post_overshoot_wrist else 'post-tip'
    if args.post_tip_elbow:
        if args.elbow_only or args.elbow_degrees!=2 or args.elbow_local_validation:
            parser.error('Post-tip elbow comparison is exclusive')
        args.elbow_only=True;args.elbow_degrees=-7
    if args.local_tip_retract:
        if any((args.local_tip_press,args.local_tip_candidate,args.ghost_first_step,args.ghost_post_wrist,args.coordinated_candidate,args.coordinated_v2)):
            parser.error('Local tip retract is exclusive')
        args.ghost_first_step='local-tip-retract'
    if args.local_tip_candidate:
        if any((args.local_tip_press,args.ghost_first_step,args.ghost_post_wrist,args.coordinated_candidate,args.coordinated_v2)):
            parser.error('Local tip candidate is exclusive')
        args.ghost_first_step='post-transfer-candidate' if args.post_transfer_candidate else 'local-tip-candidate'
        if args.affine_interior:args.ghost_first_step='affine-interior'
    if args.local_tip_press:
        if any((args.ghost_first_step,args.ghost_post_wrist,args.coordinated_candidate,args.coordinated_v2)):
            parser.error('Local tip press is an exclusive named experiment')
        args.ghost_first_step='post-transfer-tip' if args.post_transfer_tip else 'local-tip-press'
    if args.wrist_pair_leg:
        if any((args.wrist_probe,args.wrist_post_coordinated,args.wrist_ascending,args.wrist_candidate,args.wrist_prepare,args.wrist_extended_start,args.wrist_nearby_target)):
            parser.error('Shared pair leg is exclusive')
        args.wrist_post_coordinated=True;args.wrist_ascending=args.wrist_pair_leg=='up'
        args.wrist_candidate='pair-'+args.wrist_pair_leg;args.wrist_clean=True
    if args.wrist_ascending and (not args.wrist_post_coordinated or args.wrist_nearby_target or args.wrist_prepare):parser.error('Ascending requires exclusive post-coordinated experiment')
    if args.wrist_nearby_target:
        if not args.wrist_post_coordinated or not args.wrist_candidate or args.wrist_extended_start:parser.error('Nearby wrist target requires post-coordinated candidate')
        args.wrist_candidate='nearby-target'
    if args.wrist_post_coordinated:
        if args.wrist_probe or args.wrist_prepare or args.wrist_extended_start:parser.error('Exclusive post-coordinated wrist experiment')
        args.wrist_probe='post-coordinated-ascending' if args.wrist_ascending else 'post-coordinated'
    if args.coordinated_v2 and not args.coordinated_candidate:parser.error('V2 requires coordinated candidate')
    if args.coordinated_candidate:
        if args.ghost_post_wrist or args.ghost_first_step:parser.error('Exclusive coordinated candidate required')
        args.ghost_first_step='coordinated-candidate-v2' if args.coordinated_v2 else 'coordinated-candidate'
    if args.ghost_post_wrist:
        if args.ghost_first_step:parser.error('Select only one ghost starting posture')
        args.ghost_first_step='post-wrist'
    if args.wrist_clean and not args.wrist_candidate:parser.error('Clean wrist completion requires --wrist-candidate')
    if args.wrist_extended_start:
        if not args.wrist_candidate:parser.error('Extended wrist start requires --wrist-candidate')
        args.wrist_candidate='extended-start'
    if args.wrist_prepare and (not args.wrist_probe or args.wrist_candidate):parser.error('Exclusive wrist preparation required')
    if args.wrist_candidate and not args.wrist_probe:parser.error('Wrist candidate requires wrist probe')
    if args.wrist_probe and (args.ghost_first_step or args.elbow_only or args.elbow_local_validation or args.step_mm!=2 or args.elbow_degrees!=2):
        parser.error('Wrist probe is exclusive')
    if args.ghost_first_step and (args.elbow_only or args.elbow_local_validation or args.step_mm!=2 or args.elbow_degrees!=2):
        parser.error('Ghost first step is exclusive')
    if args.mapping_sample and (not args.elbow_local_validation or args.descending_candidate or args.extended_candidate_start or args.nearby_candidate_target):
        parser.error('Mapping sample requires exclusive local validation')
    if args.revised_descending and not args.descending_candidate:
        parser.error('Revised descending requires --descending-candidate')
    if args.descending_candidate and (not args.elbow_local_validation or args.extended_candidate_start or args.nearby_candidate_target):
        parser.error('Descending candidate requires exclusive local validation')
    if args.nearby_candidate_target and (not args.elbow_local_validation or args.extended_candidate_start):
        parser.error('Nearby target requires exclusive local validation')
    if args.extended_candidate_start and not args.elbow_local_validation:
        parser.error('Extended start requires --elbow-local-validation')
    if args.elbow_local_validation:
        if not args.elbow_only or args.elbow_degrees!=2:
            parser.error('Local validation requires exclusive --elbow-only')
        args.elbow_degrees=-1 if args.extended_candidate_start else 1
        if args.nearby_candidate_target: args.elbow_degrees=3
        if args.descending_candidate: args.elbow_degrees=-4
        if args.revised_descending: args.elbow_degrees=-5
        if args.mapping_sample: args.elbow_degrees=-6
    if args.elbow_degrees!=2 and not args.elbow_only:
        parser.error('--elbow-degrees requires --elbow-only')
    if args.elbow_only and args.step_mm!=2:
        parser.error('--elbow-only cannot be combined with a different step size')
    root=Path(__file__).resolve().parents[2]
    exporter=WizardDiagnosticExporter((root/'software/runs/wizard-exports').resolve())
    exporter.prepare(create=True)
    if args.execute:
        reservations=(root/'software/runs/cartesian-reservations').resolve()
        reservations.mkdir(parents=True,exist_ok=True)
        report=run_native_vertical_trial(root=reservations,step_mm=args.step_mm,elbow_only=args.elbow_only,elbow_degrees=args.elbow_degrees,ghost_first_step=args.ghost_first_step,wrist_probe=args.wrist_probe,wrist_candidate=args.wrist_candidate,wrist_prepare=args.wrist_prepare,compensated_endpoint=args.wrist_clean or args.coordinated_candidate or args.local_tip_candidate)
    else:
        with arm_transport_lock():
            feedback=bounded_probe(retain_response=True)
        report=dict(schema='rocell.cartesian_preflight.v1',feedback=feedback,
                    status='FEEDBACK_FAILED',motion_commands=0,motion_authorized=False)
        if feedback['status']=='SUCCEEDED':
            try:
                report['preview']=(preview_elbow_isolation(feedback,elbow_degrees=args.elbow_degrees) if args.elbow_only else
                                   preview_vertical_pair(feedback,step_mm=args.step_mm))
                report['status']=report['preview']['status']
                if args.ghost_first_step:
                    if args.local_tip_candidate:
                        from rocell.application.coordinated_candidate import preview_frozen_candidate
                        report['preview']=preview_frozen_candidate(feedback,tip=True,post_transfer=args.post_transfer_candidate,affine=args.affine_interior)
                    elif args.local_tip_press or args.local_tip_retract:
                        from rocell.application.local_tip_press import preview_local_tip_press
                        report['preview']=preview_local_tip_press(feedback,retract=args.local_tip_retract,post_transfer=args.post_transfer_tip)
                    elif args.coordinated_candidate:
                        from rocell.application.coordinated_candidate import preview_frozen_candidate
                        report['preview']=preview_frozen_candidate(feedback,revised=args.coordinated_v2)
                    else:
                        from rocell.application.ghost_first_step import preview_first_step
                        report['preview']=preview_first_step(feedback,post_wrist=args.ghost_first_step=='post-wrist')
                    report['status']=report['preview']['status']
                if args.wrist_probe:
                    from rocell.application.coordinated_wrist_probe import preview_wrist_probe
                    if args.wrist_map_trial:
                        from rocell.application.wrist_map_trial import preview_map_trial
                        report['preview']=preview_map_trial(feedback,preparation=args.wrist_map_trial=='prepare',posture_transfer=args.wrist_map_trial=='transfer')
                    elif args.post_tip_wrist_candidate:
                        from rocell.application.post_tip_wrist_candidate import preview_frozen_candidate
                        report['preview']=preview_frozen_candidate(feedback,reverse=args.post_tip_wrist_reverse_candidate,post_overshoot=args.post_overshoot_wrist_candidate)
                    elif args.post_tip_wrist or args.post_tip_wrist_reverse:
                        from rocell.application.coordinated_wrist_probe import preview_post_tip_wrist
                        report['preview']=preview_post_tip_wrist(feedback,reverse=args.post_tip_wrist_reverse,post_overshoot=args.post_overshoot_wrist)
                    else:
                        report['preview']=preview_wrist_probe(feedback,candidate=args.wrist_candidate,prepare=args.wrist_prepare,post_coordinated=args.wrist_post_coordinated,ascending=args.wrist_ascending)
                    report['status']=report['preview']['status']
            except (ValueError,KeyError,TypeError):
                report['status']='REFERENCE_PREVIEW_UNAVAILABLE'
                # A generic Z preview must not survive a failed named preview.
                report.pop('preview',None)
    receipt=exporter.export(dict(mode='physical-commissioning' if args.execute else 'read-only-preflight'),[],
        attachments={'cartesian-trial.json':json.dumps(report,allow_nan=False).encode()})
    verified=verify_export(Path(receipt['path']).resolve())
    if not verified['valid']:
        raise RuntimeError('Diagnostic export verification failed; do not repeat motion')
    print(json.dumps(dict(status=report['status'],execute_requested=args.execute,
        export=receipt['path'],result=(report.get('run') or {}).get('transaction',{}).get('result'))))


if __name__=='__main__':
    main()

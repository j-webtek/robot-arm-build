"""Finite hardware-free micro policy checks for wizard display and export."""
from rocell.arm.micro_correction_simulator import scenarios
from rocell.arm.command_strategy_simulation import compare


def run_suite():
    policies=scenarios()
    strategies=compare()
    expected=dict(ideal_progress='IN_BAND',quantized_progress='IN_BAND',
        unchanged='NO_USEFUL_PROGRESS',overshoot='OVERSHOOT_NO_REVERSAL',
        delayed='FEEDBACK_DEADLINE',uncertain='FEEDBACK_FAILED_OR_MISSING',
        other_joint_drift='OTHER_JOINT_DRIFT',slow_progress='ATTEMPT_LIMIT',
        late_failure='FEEDBACK_FAILED_OR_MISSING')
    checks=[dict(name=name,expected=reason,actual=policies[name]['reason'],
                 passed=policies[name]['reason']==reason) for name,reason in expected.items()]
    for row in strategies:
        reason=('EXCURSION' if row['model']=='changing_offset' else
                'NO_USEFUL_PROGRESS' if row['model']=='deadband' or
                row['strategy']=='toward_desired_setpoint' else 'IN_BAND')
        checks.append(dict(name=row['model']+'/'+row['strategy'],expected=reason,
                           actual=row['reason'],passed=row['reason']==reason))
    return dict(schema='rocell.micro_diagnostic_suite.v1',
                status='SUCCEEDED' if all(c['passed'] for c in checks) else 'FAILED',
                checks=checks,policy_scenarios=policies,strategy_scenarios=strategies,
                hardware_access=False,motion_commands=0,native_micro_enabled=False,
                motion_authorized=False,physical_accuracy_verified=False,
                remaining_live_requirements=['same_session_command_ownership',
                    'dedicated_one_use_native_send_boundary','real_deadline_polling_and_hold',
                    'live_micro_wizard_action_and_export_integration'])

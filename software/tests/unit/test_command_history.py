from rocell.simulation.command_history import ReferenceCommandHistory,command_pose


def command(z):return dict(T=104,x=350.,y=0.,z=z,t=.1,r=.02,g=3.14,spd=.05)


def test_reference_feedback_updates_xyz_pitch_but_not_stored_roll():
    h=ReferenceCommandHistory();h.complete_reference_command(command(180.))
    feedback=command(181.9);feedback['r']=.3
    h.complete_reference_feedback(command_pose(feedback))
    r=h.preview(command(182.),command_pose(command(181.9)))
    assert r['status']=='REFERENCE_HYPOTHESES_ONLY'
    assert r['historical_trace'].samples[0].pose.z_mm==181.9
    assert r['measured_trace'].samples[0].pose.z_mm==181.9
    assert len(r['historical_trace'].samples)==len(r['measured_trace'].samples)
    assert h.last_goal.z_mm==181.9  # Preview is not simulated execution.
    assert h.last_goal.roll_rad==.02
    assert not r['motion_authorized'] and not r['installed_state_verified']


def test_feedback_without_acquisition_values_does_not_keep_stale_goal():
    h=ReferenceCommandHistory();h.complete_reference_command(command(180.))
    h.complete_reference_command(dict(T=105))
    assert h.last_goal is None
    h.complete_reference_feedback(command_pose(command(181.)))
    assert h.last_goal is None


def test_unknown_or_interrupted_history_cannot_preview_as_measured_state():
    h=ReferenceCommandHistory()
    assert h.preview(command(182.),command_pose(command(180.)))['status']=='REFERENCE_ORIGIN_UNKNOWN'
    h.complete_reference_command(command(180.));h.invalidate('TRANSPORT_UNCERTAIN')
    assert h.last_goal is None
    h.complete_reference_command(command(180.));h.complete_reference_command(dict(T=101,joint=4,rad=.1))
    assert h.last_goal is None


def test_native_t104_is_held_before_io(monkeypatch,tmp_path):
    from rocell.providers.windows import wifi_cartesian_native as native
    def forbidden(*args,**kwargs):raise AssertionError('No hardware I/O permitted')
    monkeypatch.setattr(native,'bounded_probe',forbidden)
    monkeypatch.setattr(native,'arm_transport_lock',forbidden)
    for mode in (False,'affine-interior','post-transfer-tip'):
        r=native.run_native_vertical_trial(root=tmp_path,ghost_first_step=mode)
        assert r['reason']=='T104_INTERPOLATION_START_STATE_UNQUALIFIED'
        assert r['motion_commands']==0

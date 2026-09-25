from __future__ import annotations

import math
from pathlib import Path
import sys
import threading
import unittest


SOFTWARE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOFTWARE_ROOT / "src"))

from rocell.arm import (  # noqa: E402
    ArmTransport,
    CartesianGoal,
    DeterministicFeedbackSession,
    FeedbackError,
    FeedbackNotPermittedError,
    FeedbackPermit,
    MotionNotPermittedError,
    ProtocolError,
    ProtocolEmulatorSessionError,
    ReplayTransport,
    RoArmM3,
    SerialTransport,
    TransportError,
    TransportTimeoutError,
    UnsupportedCommandError,
    parse_feedback_line,
)
from rocell.arm.protocol import decode_line, encode_line, feedback_request  # noqa: E402
from rocell.arm.protocol_emulator import (  # noqa: E402
    DeterministicProtocolController,
    ProtocolEmulatorFault,
    ProtocolEmulatorStep,
)
from rocell.rc03.build_snapshot import BuildSnapshot  # noqa: E402
from rocell.safety import SafetySupervisor  # noqa: E402


def _feedback_permit() -> FeedbackPermit:
    """Create a one-shot permit from an immutable, power-released test build."""

    snapshot = BuildSnapshot(
        manifest_id="arm-boundary-test",
        manifest_sha256="a" * 64,
        design_revision="RC03-TEST",
        active_build_id="BUILD-TEST",
        source_hashes={"source.json": "b" * 64},
        selected_routes={},
        gate_statuses={},
        hard_blockers=(),
        physical_release_status="RELEASED",
        tag_coordinate_source="nominal_layout",
        camera_exact_model=None,
        camera_state="OPEN_BLOCKING",
        safe_to_power_robot=True,
        contact_enabled=False,
    )
    return SafetySupervisor(snapshot).authorize_feedback()


class FakeSerial:
    def __init__(self, replies: list[bytes] | None = None) -> None:
        self.is_open = False
        self.port = None
        self.baudrate = None
        self.timeout = None
        self.write_timeout = None
        self.rtscts = True
        self.dsrdtr = True
        self.rts = True
        self.dtr = True
        self.open_snapshot: dict[str, object] | None = None
        self.writes: list[bytes] = []
        self.replies = list(replies or [])
        self.flush_count = 0
        self.write_error: Exception | None = None
        self.buffered_byte_count = 0

    @property
    def in_waiting(self) -> int:
        return self.buffered_byte_count

    def open(self) -> None:
        self.open_snapshot = {
            "port": self.port,
            "baudrate": self.baudrate,
            "rtscts": self.rtscts,
            "dsrdtr": self.dsrdtr,
            "rts": self.rts,
            "dtr": self.dtr,
        }
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def write(self, payload: bytes) -> int:
        self.writes.append(payload)
        if self.write_error is not None:
            raise self.write_error
        return len(payload)

    def flush(self) -> None:
        self.flush_count += 1

    def readline(self, maximum: int) -> bytes:
        if not self.replies:
            return b""
        return self.replies.pop(0)[:maximum]


class ProtocolTests(unittest.TestCase):
    def test_feedback_request_is_exact_compact_newline_json(self) -> None:
        self.assertEqual(feedback_request(), {"T": 105})
        self.assertEqual(encode_line(feedback_request()), b'{"T":105}\n')
        self.assertEqual(decode_line(b'{"T":105}\r\n'), {"T": 105})

    def test_cartesian_goal_has_explicit_units_and_opaque_spd(self) -> None:
        goal = CartesianGoal(
            x_mm=101,
            y_mm=-22.5,
            z_mm=43,
            pitch_rad=0.25,
            roll_rad=-0.5,
            gripper_rad=3.14,
            spd=-7.5,
        )
        self.assertEqual(goal.spd_coefficient, -7.5)
        self.assertEqual(
            goal.to_message(),
            {
                "T": 104,
                "x": 101.0,
                "y": -22.5,
                "z": 43.0,
                "t": 0.25,
                "r": -0.5,
                "g": 3.14,
                "spd": -7.5,
            },
        )
        self.assertEqual(
            encode_line(goal.to_message()),
            b'{"T":104,"x":101.0,"y":-22.5,"z":43.0,"t":0.25,"r":-0.5,"g":3.14,"spd":-7.5}\n',
        )

    def test_nonfinite_or_boolean_goal_values_are_rejected(self) -> None:
        fields = ("x_mm", "y_mm", "z_mm", "pitch_rad", "roll_rad", "gripper_rad", "spd")
        valid = {
            "x_mm": 1.0,
            "y_mm": 2.0,
            "z_mm": 3.0,
            "pitch_rad": 0.1,
            "roll_rad": 0.2,
            "gripper_rad": 3.14,
            "spd": 10.0,
        }
        for field in fields:
            for invalid in (math.nan, math.inf, -math.inf, True):
                with self.subTest(field=field, invalid=invalid):
                    values = {**valid, field: invalid}
                    with self.assertRaises(ProtocolError):
                        CartesianGoal(**values)
        with self.assertRaises(ProtocolError):
            encode_line({"T": 105, "future": [1.0, math.nan]})
        with self.assertRaises(ProtocolError):
            decode_line(b'{"T":105,"future":NaN}\n')

    def test_t1041_is_explicitly_rejected_in_all_generic_codec_paths(self) -> None:
        with self.assertRaises(UnsupportedCommandError):
            encode_line({"T": 1041, "x": 0})
        with self.assertRaises(UnsupportedCommandError):
            decode_line(b'{"T":1041,"x":0}\n')

    def test_line_framing_and_duplicate_fields_are_strict(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "newline terminated"):
            decode_line(b'{"T":105}')
        with self.assertRaisesRegex(ProtocolError, "more than one line"):
            decode_line(b'{"T":105}\n{"T":105}\n')
        with self.assertRaisesRegex(ProtocolError, "Duplicate"):
            decode_line(b'{"T":105,"T":105}\n')

    def test_t1051_preserves_unknown_fields_losslessly(self) -> None:
        feedback = parse_feedback_line(
            b'{"T":1051,"x":1,"y":2.5,"z":3,"b":0.1,'
            b'"firmware_new":{"mode":"test","samples":[1,2]},"flag":true}\n'
        )
        self.assertEqual((feedback.x_mm, feedback.y_mm, feedback.z_mm), (1.0, 2.5, 3.0))
        self.assertEqual(feedback.base_rad, 0.1)
        self.assertEqual(
            feedback.unknown_fields,
            {"firmware_new": {"mode": "test", "samples": [1, 2]}, "flag": True},
        )
        self.assertEqual(feedback.field("firmware_new")["samples"], [1, 2])
        with self.assertRaises(FeedbackError):
            parse_feedback_line(b'{"T":105,"x":1}\n')

    def test_full_official_t1051_fields_are_typed(self) -> None:
        feedback = parse_feedback_line(
            b'{"T":1051,"x":344.9,"y":4.7,"z":206.9,"tit":0.05,'
            b'"b":0.01,"s":0,"e":1.61,"t":0.02,"r":-0.01,"g":3.13,'
            b'"tB":-44,"tS":0,"tE":128,"tT":48,"tR":32,"tG":-20,'
            b'"torswitchB":1,"torswitchS":1,"torswitchE":1,'
            b'"torswitchT":1,"torswitchR":1,"torswitchG":0,"v":1210}\n'
        )
        self.assertEqual(feedback.endpoint_pitch_rad, 0.05)
        self.assertEqual(feedback.wrist_roll_rad, -0.01)
        self.assertEqual(feedback.gripper_rad, 3.13)
        self.assertEqual(feedback.loads_raw["elbow"], 128.0)
        self.assertEqual(feedback.torque_switches["gripper"], False)
        self.assertEqual(feedback.voltage_v, 12.1)
        self.assertEqual(feedback.unknown_fields, {})


class DeterministicFeedbackSessionTests(unittest.TestCase):
    def test_emulator_session_frames_and_parses_without_a_live_permit(self) -> None:
        session = DeterministicFeedbackSession(
            (ProtocolEmulatorStep(feedback_fields={"x": 12.5}),)
        )

        session.connect()
        response = session.request_feedback()
        session.close()

        self.assertEqual(response, {"T": 1051, "x": 12.5})
        self.assertEqual(session.writes, (b'{"T":105}\n',))
        self.assertEqual(session.open_count, 1)
        self.assertEqual(session.close_count, 1)
        self.assertFalse(session.is_open)
        self.assertNotIsInstance(session, ArmTransport)

        # Its method accepts no FeedbackPermit argument, so this simulation
        # helper cannot become a drop-in live ArmTransport escape hatch.
        with self.assertRaises(TypeError):
            session.request_feedback(_feedback_permit())  # type: ignore[call-arg]

    def test_emulator_session_quarantines_a_fault_and_closes_once(self) -> None:
        session = DeterministicFeedbackSession(
            (ProtocolEmulatorStep(ProtocolEmulatorFault.MALFORMED_JSON),)
        )
        session.connect()

        with self.assertRaises(ProtocolEmulatorSessionError):
            session.request_feedback()

        self.assertEqual(session.writes, (b'{"T":105}\n',))
        self.assertFalse(session.is_open)
        self.assertEqual(session.open_count, 1)
        self.assertEqual(session.close_count, 1)
        self.assertIsNotNone(session.last_fault)

    def test_emulator_session_rejects_a_valid_line_buffered_before_open(self) -> None:
        session = DeterministicFeedbackSession(
            (ProtocolEmulatorStep(feedback_fields={"x": 12.5}),)
        )
        session.inject_preexisting_input(b'{"T":1051,"x":99.0}\n')

        with self.assertRaisesRegex(
            ProtocolEmulatorSessionError, "before the request"
        ) as raised:
            session.connect()

        self.assertEqual(raised.exception.failure.value, "STALE_BUFFERED_INPUT")
        self.assertEqual(session.writes, ())
        self.assertEqual(session.received_lines, ())
        self.assertFalse(session.is_open)
        self.assertEqual(session.open_count, 1)
        self.assertEqual(session.close_count, 1)


class ReplayAndClientTests(unittest.TestCase):
    def test_replay_feedback_uses_real_codec_and_records_request(self) -> None:
        transport = ReplayTransport([{"T": 1051, "x": 10, "future": "kept"}])
        client = RoArmM3(transport, permit_feedback=_feedback_permit())
        feedback = client.request_feedback()
        self.assertEqual(feedback.x_mm, 10.0)
        self.assertEqual(feedback.unknown_fields, {"future": "kept"})
        self.assertEqual(transport.sent_lines, (b'{"T":105}\n',))
        self.assertEqual(transport.pending_response_count, 0)

    def test_motion_without_explicit_true_permit_never_writes(self) -> None:
        goal = CartesianGoal(1, 2, 3, 0.1, 0.0, 3.14, 5)
        for callback in (None, lambda _goal: False, lambda _goal: True, object()):
            with self.subTest(callback=callback):
                transport = ReplayTransport()
                client = RoArmM3(transport, permit_motion=callback)  # type: ignore[arg-type]
                with self.assertRaises(MotionNotPermittedError):
                    client.move_cartesian(goal)
                self.assertEqual(transport.sent_lines, ())

    def test_replay_exhaustion_is_one_request_without_retry(self) -> None:
        transport = ReplayTransport()
        client = RoArmM3(transport, permit_feedback=_feedback_permit())
        with self.assertRaises(TransportTimeoutError):
            client.request_feedback()
        self.assertEqual(transport.sent_lines, (b'{"T":105}\n',))

    def test_feedback_without_one_shot_permit_never_records_request(self) -> None:
        transport = ReplayTransport([{"T": 1051}])
        client = RoArmM3(transport)
        with self.assertRaises(FeedbackNotPermittedError):
            client.request_feedback()
        self.assertEqual(transport.sent_lines, ())
        self.assertEqual(transport.pending_response_count, 1)

    def test_feedback_permit_is_consumed_exactly_once(self) -> None:
        transport = ReplayTransport([{"T": 1051}, {"T": 1051}])
        client = RoArmM3(transport, permit_feedback=_feedback_permit())
        client.request_feedback()
        with self.assertRaises(FeedbackNotPermittedError):
            client.request_feedback()
        self.assertEqual(transport.sent_lines, (b'{"T":105}\n',))
        self.assertEqual(transport.pending_response_count, 1)


class SerialTransportTests(unittest.TestCase):
    def test_live_transport_is_lazy_and_sets_rts_dtr_false_before_open(self) -> None:
        fake = FakeSerial([b'{"T":1051,"x":12}\r\n'])
        factory_calls: list[None] = []

        def factory() -> FakeSerial:
            factory_calls.append(None)
            return fake

        transport = SerialTransport("COM_TEST", serial_factory=factory)
        self.assertFalse(transport.is_open)
        self.assertEqual(factory_calls, [])
        self.assertFalse(hasattr(transport, "send"))
        self.assertFalse(hasattr(transport, "exchange"))
        with self.assertRaises(FeedbackNotPermittedError):
            transport.request_feedback(None)

        transport.connect()
        self.assertEqual(len(factory_calls), 1)
        self.assertEqual(
            fake.open_snapshot,
            {
                "port": "COM_TEST",
                "baudrate": 115200,
                "rtscts": False,
                "dsrdtr": False,
                "rts": False,
                "dtr": False,
            },
        )
        response = transport.request_feedback(_feedback_permit())
        self.assertEqual(response, {"T": 1051, "x": 12})
        self.assertEqual(fake.writes, [b'{"T":105}\n'])
        transport.close()
        self.assertFalse(transport.is_open)

    def test_serial_failure_is_not_retried_and_connection_is_quarantined(self) -> None:
        fake = FakeSerial()
        fake.write_error = OSError("injected write failure")
        factory_count = 0

        def factory() -> FakeSerial:
            nonlocal factory_count
            factory_count += 1
            return fake

        transport = SerialTransport("COM_TEST", serial_factory=factory)
        transport.connect()
        permit = _feedback_permit()
        with self.assertRaisesRegex(TransportError, "injected write failure"):
            transport.request_feedback(permit)
        self.assertEqual(factory_count, 1)
        self.assertEqual(fake.writes, [b'{"T":105}\n'])
        self.assertFalse(transport.is_open)
        self.assertIn("injected write failure", transport.last_fault or "")
        self.assertTrue(permit.consumed)

    def test_stale_valid_feedback_is_rejected_during_connect(self) -> None:
        fake = FakeSerial([b'{"T":1051,"x":99.0}\n'])
        fake.buffered_byte_count = len(fake.replies[0])
        transport = SerialTransport("COM_TEST", serial_factory=lambda: fake)

        with self.assertRaisesRegex(TransportError, "after open"):
            transport.connect()

        self.assertFalse(transport.is_open)
        self.assertEqual(fake.writes, [])
        self.assertIn("after open", transport.last_fault or "")

    def test_stale_valid_feedback_is_rejected_before_a_new_live_request(self) -> None:
        fake = FakeSerial([b'{"T":1051,"x":99.0}\n'])
        transport = SerialTransport("COM_TEST", serial_factory=lambda: fake)
        transport.connect()
        fake.buffered_byte_count = len(fake.replies[0])
        permit = _feedback_permit()

        with self.assertRaisesRegex(TransportError, "before the request"):
            transport.request_feedback(permit)

        self.assertTrue(permit.consumed)
        self.assertEqual(fake.writes, [])
        self.assertFalse(transport.is_open)
        self.assertIn("before the request", transport.last_fault or "")

    def test_bad_feedback_lines_are_quarantined_before_a_followup_request(self) -> None:
        faults = (
            ProtocolEmulatorFault.OVERLONG_LINE,
            ProtocolEmulatorFault.TRUNCATED_LINE,
            ProtocolEmulatorFault.MALFORMED_JSON,
            ProtocolEmulatorFault.INVALID_TYPED_FEEDBACK,
            ProtocolEmulatorFault.WRONG_RESPONSE_TYPE,
        )
        for fault in faults:
            with self.subTest(fault=fault.value):
                bad_permit = _feedback_permit()
                controller = DeterministicProtocolController(
                    (
                        ProtocolEmulatorStep(fault),
                        ProtocolEmulatorStep(
                            feedback_fields={"x": 12.5, "emulator_case": fault.value}
                        ),
                    )
                )
                transport = SerialTransport(
                    "COM_TEST",
                    max_line_bytes=96,
                    serial_factory=lambda: controller,
                )
                transport.connect()

                with self.assertRaises(TransportError):
                    transport.request_feedback(bad_permit)

                self.assertTrue(bad_permit.consumed)
                self.assertFalse(transport.is_open)
                self.assertEqual(controller.writes, (b'{"T":105}\n',))
                self.assertEqual(controller.pending_step_count, 1)

                # A consumed permit cannot turn the failed transaction into a
                # blind retry, and no unread suffix is available while closed.
                with self.assertRaises(FeedbackNotPermittedError):
                    transport.request_feedback(bad_permit)
                self.assertEqual(controller.writes, (b'{"T":105}\n',))

                # Recovery is an explicit reconnect plus a newly issued permit.
                transport.connect()
                response = transport.request_feedback(_feedback_permit())
                self.assertEqual(response["T"], 1051)
                self.assertEqual(response["x"], 12.5)
                self.assertEqual(len(controller.writes), 2)

    def test_partial_write_faults_closed_and_consumes_one_permit(self) -> None:
        permit = _feedback_permit()
        controller = DeterministicProtocolController(
            (ProtocolEmulatorStep(ProtocolEmulatorFault.PARTIAL_WRITE),)
        )
        transport = SerialTransport("COM_TEST", serial_factory=lambda: controller)
        transport.connect()

        with self.assertRaisesRegex(TransportError, "Partial serial write"):
            transport.request_feedback(permit)

        self.assertTrue(permit.consumed)
        self.assertFalse(transport.is_open)
        self.assertEqual(controller.writes, (b'{"T":105}\n',))

    def test_timeout_disconnect_and_reset_each_require_explicit_reconnect(self) -> None:
        for fault in (
            ProtocolEmulatorFault.TIMEOUT,
            ProtocolEmulatorFault.DISCONNECT,
            ProtocolEmulatorFault.RESET_BANNER,
        ):
            with self.subTest(fault=fault.value):
                controller = DeterministicProtocolController(
                    (ProtocolEmulatorStep(fault),)
                )
                transport = SerialTransport(
                    "COM_TEST", serial_factory=lambda: controller
                )
                transport.connect()
                permit = _feedback_permit()

                with self.assertRaises(TransportError):
                    transport.request_feedback(permit)

                self.assertTrue(permit.consumed)
                self.assertFalse(transport.is_open)
                self.assertEqual(controller.open_count, 1)
                self.assertGreaterEqual(controller.close_count, 1)

    def test_concurrent_close_waits_for_the_owned_feedback_transaction(self) -> None:
        controller = DeterministicProtocolController(
            (ProtocolEmulatorStep(feedback_fields={"x": 9.0}),),
            block_reads=True,
        )
        transport = SerialTransport("COM_TEST", serial_factory=lambda: controller)
        transport.connect()
        result: list[dict[str, object]] = []
        request_errors: list[BaseException] = []
        close_finished = threading.Event()

        def request() -> None:
            try:
                result.append(transport.request_feedback(_feedback_permit()))
            except BaseException as exc:  # pragma: no cover - asserted below
                request_errors.append(exc)

        def close() -> None:
            transport.close()
            close_finished.set()

        request_thread = threading.Thread(target=request)
        request_thread.start()
        self.assertTrue(controller.read_started.wait(timeout=1.0))
        close_thread = threading.Thread(target=close)
        close_thread.start()
        self.assertFalse(close_finished.wait(timeout=0.05))

        controller.allow_read()
        request_thread.join(timeout=2.0)
        close_thread.join(timeout=2.0)

        self.assertFalse(request_thread.is_alive())
        self.assertFalse(close_thread.is_alive())
        self.assertEqual(request_errors, [])
        self.assertEqual(result[0]["x"], 9.0)
        self.assertTrue(close_finished.is_set())
        self.assertFalse(transport.is_open)

    def test_replay_wrong_type_or_invalid_typed_feedback_faults_closed(self) -> None:
        for bad in ({"T": 105}, {"T": 1051, "x": "bad"}):
            with self.subTest(bad=bad):
                permit = _feedback_permit()
                transport = ReplayTransport((bad, {"T": 1051, "x": 3.0}))
                with self.assertRaises(TransportError):
                    transport.request_feedback(permit)
                self.assertTrue(permit.consumed)
                self.assertFalse(transport.is_open)
                self.assertEqual(transport.pending_response_count, 1)

                transport.connect()
                self.assertEqual(
                    transport.request_feedback(_feedback_permit())["x"], 3.0
                )

    def test_live_motion_is_hard_blocked_even_at_direct_transport_boundary(self) -> None:
        fake = FakeSerial()
        transport = SerialTransport("COM_TEST", serial_factory=lambda: fake)
        transport.connect()
        goal = CartesianGoal(1, 2, 3, 0.1, 0.0, 1.0, 0.25)

        with self.assertRaisesRegex(MotionNotPermittedError, "bounded-goal"):
            transport.send_motion(goal, None)
        self.assertEqual(fake.writes, [])

    def test_raw_codec_helpers_are_not_public_arm_package_exports(self) -> None:
        import rocell.arm as arm

        for raw_name in ("encode_line", "decode_line", "feedback_request"):
            with self.subTest(raw_name=raw_name):
                self.assertFalse(hasattr(arm, raw_name))


if __name__ == "__main__":
    unittest.main()

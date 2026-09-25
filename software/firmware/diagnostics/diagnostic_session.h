// Finite owner-side session. Native callers must provide admission and a bounded,
// loss-detecting evidence sink; a successful publish is not a host disk export.
#pragma once
#include "reference_write_capture.h"
#include "reference_read_adapter.h"

namespace rocell_diag {
enum class SessionState { Idle, Sampling, Captured, Fault };
class DiagnosticSession {
 public:
  DiagnosticSession() : state_(SessionState::Idle), remaining_(0), reason_("NONE"),
      interval_(0),next_due_(0),last_poll_(0) {}
  DiagnosticSession(const DiagnosticSession&)=delete;
  DiagnosticSession& operator=(const DiagnosticSession&)=delete;

  template<class Library,class Clock,class Sink>
  bool start(Library& library,Clock& clock,Sink& sink,const char* boot,
      const char* command,uint8_t servo,uint16_t target,uint16_t speed,
      uint8_t acceleration,uint16_t samples,uint64_t pair_budget,
      uint64_t interval_us=1000000,WriteBoundaryGuard guard={}) {
    if (state_!=SessionState::Idle) { fail("DUPLICATE_START");return false; }
    if (!valid_identity(boot) || !valid_identity(command) || servo<1 || servo>253 ||
        target>4095 || !speed || !acceleration || !samples || samples>2000 ||
        !pair_budget || pair_budget>interval_us || interval_us<1000 || interval_us>60000000) {
      fail("INVALID_INPUT");return false;
    }
    if (library.End!=0) { fail("UNSUPPORTED_BYTE_ORDER");return false; }
    // Four write-boundary records plus every requested pair must fit before
    // movement. A sink can still fail later; those failures remain terminal.
    if (!sink.reserve(static_cast<size_t>(samples)+4)) { fail("EVIDENCE_CAPACITY");return false; }
    // Retain correlation BEFORE dispatch. This is the post-conversion boundary,
    // not proof of original HTTP payload or physical workspace admission.
    const int n=snprintf(buffer_,sizeof(buffer_),
        "{\"schema\":\"rocell.converted_command.v2\",\"boot_id\":\"%s\","
        "\"command_id\":\"%s\",\"servo_id\":%u,\"wire_count\":%u,"
        "\"speed\":%u,\"acceleration\":%u,\"sample_count\":%u,"
        "\"sample_interval_us\":%llu,\"maximum_lateness_us\":%llu,\"maximum_pair_us\":%llu}",
        boot,command,servo,target,speed,acceleration,samples,
        (unsigned long long)interval_us,(unsigned long long)interval_us,(unsigned long long)pair_budget);
    if (n<0 || static_cast<size_t>(n)>=sizeof(buffer_) || !sink.publish("converted",buffer_)) {
      fail("EVIDENCE_FAILURE");return false;
    }
    const bool dispatched=hook_.dispatch(library,clock,boot,command,servo,target,
        speed,acceleration,samples,pair_budget,guard);
    // Preserve failed write facts too; never retry a write to obtain evidence.
    if (!hook_.encode_outcome(buffer_,sizeof(buffer_)) || !sink.publish("hook",buffer_)) {
      fail("EVIDENCE_FAILURE");return false;
    }
    // A denied boundary has no bus result. Keep its hook record, never fabricate
    // dispatch/ACK evidence to fill the successful-session prefix.
    if (!hook_.write_attempted()) {fail("WRITE_NOT_ATTEMPTED");return false;}
    if (!hook_.capture().encode_dispatch(buffer_,sizeof(buffer_)) || !sink.publish("dispatch",buffer_) ||
        !hook_.capture().encode_write_evidence(buffer_,sizeof(buffer_)) || !sink.publish("write",buffer_)) {
      fail("EVIDENCE_FAILURE");return false;
    }
    if (!dispatched) { fail("WRITE_NOT_VERIFIED");return false; }
    interval_=interval_us;last_poll_=hook_.capture().dispatch_finished_us();
    if (last_poll_>static_cast<uint64_t>(INT64_MAX)-2*interval_) {
      fail("INVALID_CLOCK");return false;
    }
    next_due_=last_poll_+interval_;
    remaining_=samples;state_=SessionState::Sampling;return true;
  }

  template<class Library,class Clock,class Sink>
  bool sample(Library& library,Clock& clock,Sink& sink) {
    if (state_!=SessionState::Sampling) return false;
    const uint64_t now=clock.now_us();
    if (now<last_poll_ || now>INT64_MAX) {fail("INVALID_CLOCK");return false;}
    last_poll_=now;
    if (now<next_due_) return false; // Not due; caller inspects state, no bus I/O.
    if (now-next_due_>interval_) {fail("MISSED_SAMPLE_DEADLINE");return false;}
    ReferenceReadAdapter<Library> adapter(library);PairEvidence pair;
    const bool valid=hook_.capture().acquire(adapter,clock,pair);
    if (!hook_.capture().encode_pair("little",buffer_,sizeof(buffer_)) ||
        !sink.publish("pair",buffer_)) { fail("EVIDENCE_FAILURE");return false; }
    if (!valid) { fail("INVALID_ACQUISITION");return false; }
    // The pinned adapter admits little-endian reads only. Retain the complete
    // pair above, then stop if the servo goal differs from the actual write.
    // This is target-register evidence, not proof of physical endpoint arrival.
    const uint16_t readback=static_cast<uint16_t>(pair.target.bytes[0]) |
        (static_cast<uint16_t>(pair.target.bytes[1])<<8);
    if(readback!=hook_.capture().wire_count()){
      fail("TARGET_READBACK_MISMATCH");return false;
    }
    if (pair.target.started_us<now || pair.feedback.finished_us<now ||
        pair.feedback.finished_us>static_cast<uint64_t>(INT64_MAX)-2*interval_) {
      fail("INVALID_CLOCK");return false;
    }
    last_poll_=pair.feedback.finished_us;
    // Schedule from actual finish; never issue a catch-up burst of stale cadence.
    next_due_=last_poll_+interval_;
    if (--remaining_==0) { state_=SessionState::Captured;hook_.capture().stop(); }
    return true; // Captured does not mean settled, accurate or host-exported.
  }
  void interference() { fail("INTERFERING_COMMAND"); }
  void export_failed() { fail("EVIDENCE_FAILURE"); }
  SessionState state() const { return state_; }
  const char* reason() const { return reason_; }
 private:
  void fail(const char* reason) {
    if (state_!=SessionState::Fault) reason_=reason;
    state_=SessionState::Fault;hook_.capture().stop();
  }
  SessionState state_;
  uint16_t remaining_;
  const char* reason_;
  uint64_t interval_,next_due_,last_poll_;
  ReferenceWriteCapture hook_;
  char buffer_[2048];
};
} // namespace rocell_diag

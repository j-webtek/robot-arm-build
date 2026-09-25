// Candidate hook for the pinned SMS_STS WritePosEx API. No global bus or startup.
#pragma once
#include "command_capture.h"

namespace rocell_diag {
// Final owner-side predicate. Must be nonblocking and perform no bus I/O/writes.
// Empty is legacy behavior; authenticated v3 adapters must supply a real guard.
struct WriteBoundaryGuard {
  bool (*check)(void*,uint64_t)=nullptr;
  void* context=nullptr;
};
class ReferenceWriteCapture {
 public:
  ReferenceWriteCapture() : used_(false), attempted_(false), before_(0), after_(0),
      status_("NOT_STARTED") {}
  ReferenceWriteCapture(const ReferenceWriteCapture&)=delete;
  ReferenceWriteCapture& operator=(const ReferenceWriteCapture&)=delete;

  // Call IN PLACE OF the original write, only from the admitted bus owner.
  // This is not trajectory admission: caller must validate workspace/speed bounds.
  // Inputs are the actual post-conversion positive single-turn target, not radians.
  template<class Library,class Clock>
  bool dispatch(Library& library,Clock& clock,const char* boot,const char* command,
      uint8_t servo,uint16_t target,uint16_t speed,uint8_t acceleration,
      uint16_t sample_limit,uint64_t pair_limit_us,WriteBoundaryGuard guard={}) {
    if (used_) return false;
    used_=true; // Also consumes invalid attempts; no automatic reuse/retry.
    status_="REJECTED_INPUT";
    if (!valid_identity(boot) || !valid_identity(command) || servo<1 || servo>253 ||
        target>4095 || speed==0 || acceleration==0 || sample_limit==0 ||
        sample_limit>2000 || pair_limit_us==0 || pair_limit_us>INT64_MAX) {
      capture_.stop();return false;
    }
    char owned_boot[129],owned_command[129];
    memcpy(owned_boot,boot,strlen(boot)+1);
    memcpy(owned_command,command,strlen(command)+1);
    const uint64_t before=clock.now_us();
    before_=before;
    if (before>INT64_MAX) { status_="INVALID_CLOCK";capture_.stop();return false; }
    if (guard.check && !guard.check(guard.context,before)) {
      status_="PREWRITE_REJECTED";capture_.stop();return false;
    }
    const AckPolicy ack=library.Level?AckPolicy::Enabled:AckPolicy::Disabled;
    attempted_=true;
    const int result=library.WritePosEx(servo,static_cast<int16_t>(target),speed,acceleration);
    // Sample Error immediately, before any feedback call can replace it. Without
    // a valid reply, Error is unavailable even if the library resets it to zero.
    const int error=(ack==AckPolicy::Enabled && result==1)?library.Error:-1;
    const uint64_t after=clock.now_us();
    after_=after;
    const bool clock_valid=after>=before && after<=INT64_MAX;
    capture_.begin(owned_boot,owned_command,servo,target,speed,acceleration,
        clock_valid?after:before,result,error,ack,sample_limit,pair_limit_us);
    if (!clock_valid) capture_.stop();
    status_=!clock_valid?"INVALID_CLOCK":capture_.stopped()?"WRITE_NOT_VERIFIED":"WRITE_VERIFIED";
    return !capture_.stopped();
  }
  // Local hook outcome is separate from ACK status: a valid ACK cannot erase a
  // timing fault. Raw clocks are strings to preserve the full uint64 range.
  bool encode_outcome(char* output,size_t capacity) const {
    if (!output || !capacity) return false;
    output[0]=0;
    const int n=snprintf(output,capacity,
        "{\"schema\":\"rocell.write_hook_outcome.v1\",\"status\":\"%s\","
        "\"write_attempted\":%s,\"started_us_raw\":\"%llu\","
        "\"finished_us_raw\":\"%llu\",\"capture_stopped\":%s}",
        status_,attempted_?"true":"false",(unsigned long long)before_,
        (unsigned long long)after_,capture_.stopped()?"true":"false");
    if (n<0 || static_cast<size_t>(n)>=capacity) { output[0]=0;return false; }
    return true;
  }
  CommandCapture& capture() { return capture_; }
  bool write_attempted() const {return attempted_;}
 private:
  bool used_;
  bool attempted_;
  uint64_t before_,after_;
  const char* status_;
  CommandCapture capture_;
};
} // namespace rocell_diag

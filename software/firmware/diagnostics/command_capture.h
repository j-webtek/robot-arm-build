// One-command diagnostic capture. Does not dispatch motion or own a native bus.
#pragma once
#include "servo_evidence_json.h"

namespace rocell_diag {
class CommandCapture {
 public:
  CommandCapture() : started_(false), stopped_(false), captured_(false), samples_(0), limit_(0),
      wire_count_(0), speed_(0), acceleration_(0), dispatch_us_(0), pair_limit_us_(0),
      evidence_{}, boot_{}, command_{}, last_{} {}

  // Hook AFTER the one real controller write. Preserve its actual conversion,
  // settings and return; this method performs no write, retry or target conversion.
  bool begin(const char* boot, const char* command, uint8_t servo, uint16_t target,
      uint16_t speed, uint8_t acceleration, uint64_t dispatch_us,
      int write_return, int device_error, AckPolicy ack,
      uint16_t sample_limit, uint64_t pair_limit_us) {
    if (started_ || stopped_ || !valid_identity(boot) || !valid_identity(command) ||
        servo<1 || servo>253 || speed==0 || acceleration==0 ||
        dispatch_us>INT64_MAX || sample_limit==0 || sample_limit>2000 ||
        pair_limit_us==0 || pair_limit_us>INT64_MAX) {
      stopped_=true; return false;
    }
    memcpy(boot_,boot,strlen(boot)+1);memcpy(command_,command,strlen(command)+1);
    evidence_=record_dispatch(servo,write_return,device_error,ack);
    wire_count_=target;speed_=speed;acceleration_=acceleration;
    dispatch_us_=dispatch_us;limit_=sample_limit;pair_limit_us_=pair_limit_us;
    started_=true;
    stopped_=evidence_.status!=DispatchStatus::Succeeded;
    return true; // Means retained, not verified delivery. Inspect evidence/status.
  }

  template <class Bus,class Clock>
  bool acquire(Bus& bus,Clock& clock,PairEvidence& pair) {
    pair={};
    if (!started_ || stopped_ || samples_>=limit_) { stopped_=true; return false; }
    const bool valid=recorder_.acquire(evidence_.servo_id,bus,clock,pair);
    last_=pair;captured_=true;
    ++samples_;
    if (!valid || pair.target.started_us<=dispatch_us_ ||
        pair.feedback.finished_us<pair.target.started_us ||
        pair.feedback.finished_us-pair.target.started_us>pair_limit_us_) {
      stopped_=true;return false;
    }
    return true;
  }

  bool encode_pair(const char* byte_order,
                   char* output,size_t capacity) const {
    if (output && capacity) output[0]=0;
    if (!started_ || !captured_) return false;
    // Retain a failed acquisition for export even after progression stops.
    return pair_json(last_,boot_,command_,byte_order,output,capacity);
  }

  bool encode_dispatch(char* output,size_t capacity) const {
    if (!output || !capacity) return false;
    output[0]=0;
    if (!started_) return false;
    const char* status=evidence_.status==DispatchStatus::Succeeded?"SUCCEEDED":
        evidence_.status==DispatchStatus::Failed?"FAILED":"UNKNOWN";
    const int n=snprintf(output,capacity,
        "{\"boot_id\":\"%s\",\"command_id\":\"%s\",\"servo_id\":%u,"
        "\"wire_count\":%u,\"speed\":%u,\"acceleration\":%u,"
        "\"device_us\":%llu,\"bus_write_status\":\"%s\"}",
        boot_,command_,evidence_.servo_id,wire_count_,speed_,acceleration_,
        (unsigned long long)dispatch_us_,status);
    if (n<0 || static_cast<size_t>(n)>=capacity) { output[0]=0;return false; }
    return true;
  }

  bool stopped() const { return stopped_; }
  uint64_t dispatch_finished_us() const { return dispatch_us_; }
  uint16_t wire_count() const { return wire_count_; }
  void stop() { stopped_=true; } // External owner/export/clock fault; never resumes.
  // Separate versioned record preserves facts omitted by the legacy dispatch
  // schema. A library return of 1 without enabled ACK is not delivery proof.
  bool encode_write_evidence(char* output,size_t capacity) const {
    if (!output || !capacity) return false;
    output[0]=0;
    if (!started_) return false;
    const char* ack=evidence_.ack_policy==AckPolicy::Enabled?"ENABLED":
        evidence_.ack_policy==AckPolicy::Disabled?"DISABLED":"UNKNOWN";
    const char* status=evidence_.status==DispatchStatus::Succeeded?"SUCCEEDED":
        evidence_.status==DispatchStatus::Failed?"FAILED":"UNKNOWN";
    const int n=snprintf(output,capacity,
        "{\"schema\":\"rocell.servo_write_evidence.v1\","
        "\"boot_id\":\"%s\",\"command_id\":\"%s\",\"servo_id\":%u,"
        "\"device_us\":%llu,\"library_return\":%d,\"device_error\":%d,"
        "\"ack_policy\":\"%s\",\"bus_write_status\":\"%s\"}",
        boot_,command_,evidence_.servo_id,(unsigned long long)dispatch_us_,
        evidence_.library_return,evidence_.device_error,ack,status);
    if (n<0 || static_cast<size_t>(n)>=capacity) { output[0]=0;return false; }
    return true;
  }
  const DispatchEvidence& write_evidence() const { return evidence_; }

 private:
  bool started_,stopped_,captured_;
  uint16_t samples_,limit_,wire_count_,speed_;
  uint8_t acceleration_;
  uint64_t dispatch_us_,pair_limit_us_;
  DispatchEvidence evidence_;
  char boot_[129],command_[129];
  PairEvidence last_;
  PairRecorder recorder_;
};
} // namespace rocell_diag

// Offline-tested producer primitives. Not an installed firmware patch.
// No Arduino dependency, global bus, startup code, retries or configuration writes.
#pragma once
#include <stdint.h>

namespace rocell_diag {
enum class AckPolicy { Unknown, Disabled, Enabled };
enum class DispatchStatus { Unknown, Failed, Succeeded };
enum class ReadStatus { Failed, Succeeded };

struct DispatchEvidence {
  uint8_t servo_id;
  int library_return;
  int device_error;
  AckPolicy ack_policy;
  DispatchStatus status;
};

// The pinned SCS::Ack returns 1 without reading a response for Level==0
// or broadcast ID 254. Neither is an observed servo acknowledgment.
inline DispatchEvidence record_dispatch(uint8_t id, int result, int error,
                                        AckPolicy policy) {
  DispatchStatus status = DispatchStatus::Unknown;
  if (id >= 1 && id <= 253 && policy == AckPolicy::Enabled) {
    if (result == 0 || (result == 1 && error > 0 && error <= 255))
      status = DispatchStatus::Failed;
    else if (result == 1 && error == 0)
      status = DispatchStatus::Succeeded;
  }
  return {id, result, error, policy, status};
}

struct BusReadResult {
  int returned_bytes;
  int device_error;  // -1 means unavailable, not zero/success.
};

struct ReadEvidence {
  uint8_t servo_id;
  uint8_t address;
  uint8_t width;
  uint32_t sequence;
  uint64_t started_us;
  uint64_t finished_us;
  int returned_bytes;
  int device_error;
  ReadStatus status;
  uint8_t bytes[15];
};

struct PairEvidence { ReadEvidence target; ReadEvidence feedback; };

// Called by the controller's existing bus owner only. Identity (boot/command),
// reviewed profile and dispatch boundary must be attached by the outer adapter.
// Native binding and concurrent-owner protection are NOT provided by this class.
class PairRecorder {
 public:
  PairRecorder() : sequence_(0), last_finished_us_(0), faulted_(false) {}
  bool faulted() const { return faulted_; }

  template <class Bus, class Clock>
  bool acquire(uint8_t id, Bus& bus, Clock& clock, PairEvidence& pair) {
    // No calls occur once a previous acquisition failed. No automatic retry.
    pair = {};
    if (faulted_ || id < 1 || id > 253 || sequence_ > UINT32_MAX - 2) {
      faulted_ = true;
      return false;
    }
    pair.target = read(id, 42, 2, bus, clock);
    // Collect the bounded pair even when the first read fails, so the caller can
    // preserve both outcomes. This does not issue a write or restart the sequence.
    pair.feedback = read(id, 56, 15, bus, clock);
    faulted_ = pair.target.status != ReadStatus::Succeeded ||
               pair.feedback.status != ReadStatus::Succeeded ||
               // Adjacent synchronous reads can share a quantized microsecond.
               // Preserve the initial positive-time check and reject reversals.
               (pair.target.sequence==0 ? pair.target.started_us==0 :
                  pair.target.started_us < last_finished_us_) ||
               pair.feedback.started_us < pair.target.finished_us;
    last_finished_us_ = pair.feedback.finished_us;
    return !faulted_;
  }

 private:
  uint32_t sequence_;
  uint64_t last_finished_us_;
  bool faulted_;

  template <class Bus, class Clock>
  ReadEvidence read(uint8_t id, uint8_t address, uint8_t width,
                    Bus& bus, Clock& clock) {
    ReadEvidence record = {};
    record.servo_id = id; record.address = address; record.width = width;
    record.sequence = sequence_++;
    record.started_us = clock.now_us();
    // Each call receives a new zeroed destination; stale cache is never copied.
    const BusReadResult result = bus.read(id, address, width, record.bytes);
    record.finished_us = clock.now_us();
    record.returned_bytes = result.returned_bytes;
    record.device_error = result.device_error;
    record.status = result.returned_bytes == width && result.device_error == 0 &&
                    record.finished_us >= record.started_us
        ? ReadStatus::Succeeded : ReadStatus::Failed;
    if (record.status == ReadStatus::Failed)
      for (uint8_t& byte : record.bytes) byte = 0;
    // A serializer MUST emit raw_hex:null on failure, not these cleared bytes.
    return record;
  }
};
}  // namespace rocell_diag

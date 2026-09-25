// Bounded callback-to-owner handoff, not a command executor or a bus lock.
#pragma once
#include <atomic>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace rocell_diag {
template <size_t PacketBytes,size_t Capacity=4>
class CallbackHandoff {
  static_assert(PacketBytes>0 && PacketBytes<=256,"Bounded packet size required");
  static_assert(Capacity>0 && Capacity<=16,"Bounded queue required");
 public:
  struct Packet { uint8_t sender[6]; uint8_t bytes[PacketBytes]; };
  CallbackHandoff() : fault_(false),head_(0),size_(0) {}
  CallbackHandoff(const CallbackHandoff&)=delete;
  CallbackHandoff& operator=(const CallbackHandoff&)=delete;

  // Never wait/spin or call device code in a Wi-Fi callback. A dropped command
  // makes progression uncertain: latch a fault instead of silently replacing it.
  bool push(const uint8_t* sender,const uint8_t* data,size_t bytes) {
    if (fault_.load()) return false;
    if (!sender || !data || bytes!=PacketBytes) { fault_.store(true);return false; }
    if (lock_.test_and_set(std::memory_order_acquire)) { fault_.store(true);return false; }
    if (fault_.load() || size_==Capacity) {
      fault_.store(true);lock_.clear(std::memory_order_release);return false;
    }
    Packet& slot=packets_[(head_+size_)%Capacity];
    memcpy(slot.sender,sender,6);memcpy(slot.bytes,data,PacketBytes);++size_;
    lock_.clear(std::memory_order_release);
    return true;
  }

  // Call only from the single designated control-loop owner. Pop never executes
  // the packet. Admission/identity/payload validation is still required there.
  bool pop(Packet& output) {
    output={};
    if (fault_.load() || lock_.test_and_set(std::memory_order_acquire)) return false;
    if (fault_.load() || !size_) { lock_.clear(std::memory_order_release);return false; }
    output=packets_[head_];packets_[head_]={};head_=(head_+1)%Capacity;--size_;
    lock_.clear(std::memory_order_release);
    return true;
  }
  bool faulted() const { return fault_.load(); }
  // Deliberately no reset/replay method. Owner records fault and stops the trial.
 private:
  std::atomic_flag lock_=ATOMIC_FLAG_INIT;
  std::atomic<bool> fault_;
  size_t head_,size_;
  Packet packets_[Capacity]={};
};
} // namespace rocell_diag

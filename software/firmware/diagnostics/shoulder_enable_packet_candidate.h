// Offline candidate only: not wired into installed firmware or HTTP routes.
// A broadcast has no per-servo acknowledgement. Calling code must independently
// validate fresh preloaded goals and verify BOTH servos after this one attempt.
#pragma once
#include <cstdint>
namespace rocell_diag {
enum class ShoulderEnableDelivery { NotAttempted, SentUnacknowledged };
class ShoulderEnablePacketCandidate {
 public:
  template<class Bus> ShoulderEnableDelivery emit_once(Bus& bus) {
    if(attempted_)return ShoulderEnableDelivery::NotAttempted;
    attempted_=true; // Consume before the potentially uncertain transmission.
    uint8_t ids[2]={12,13}, enabled[2]={1,1};
    bus.syncWrite(ids,2,40,enabled,1);
    return ShoulderEnableDelivery::SentUnacknowledged;
  }
 private:
  bool attempted_=false;
};
}

// Included after the pinned reference's struct_message definition. Candidate only.
// The callback copies bytes; all parsing and bus-affecting handlers run in loop().
#include "callback_handoff.h"

rocell_diag::CallbackHandoff<sizeof(struct_message)> rocellEspNowQueue;
bool rocellOwnerRejected=false; // Accessed only by the control-loop owner.
bool rocellOwnerFault() { return rocellOwnerRejected || rocellEspNowQueue.faulted(); }

void OnDataRecv(const esp_now_recv_info_t* info,const unsigned char* data,int length) {
  rocellEspNowQueue.push(info ? info->src_addr : nullptr,data,
      length<0 ? 0 : static_cast<size_t>(length));
}

void processEspNowOwner() {
  if (rocellOwnerFault()) return;
  rocell_diag::CallbackHandoff<sizeof(struct_message)>::Packet packet;
  if (!rocellEspNowQueue.pop(packet)) return;
  // Mutable configuration is read by the owner, never by the Wi-Fi callback.
  if (espNowMode!=3 || (!ctrlByBroadcast &&
      memcmp(packet.sender,mac_whitelist_broadcast,6)!=0)) return;
  struct_message message;
  memcpy(&message,packet.bytes,sizeof(message));
  if (message.cmd>3) { rocellOwnerRejected=true;return; }
  if (message.cmd==0) {
    if (!isfinite(message.base) || !isfinite(message.shoulder) ||
        !isfinite(message.elbow) || !isfinite(message.wrist) ||
        !isfinite(message.roll) || !isfinite(message.hand)) {
      rocellOwnerRejected=true;return;
    }
    if (!rocellOwnerFault()) RoArmM3_allJointAbsCtrl(message.base,message.shoulder,
        message.elbow,message.wrist,message.roll,message.hand,0,0);
  } else {
    if (!memchr(message.message,0,sizeof(message.message))) {
      rocellOwnerRejected=true;return;
    }
    if (message.cmd==3) { Serial.println(message.message);return; }
    jsonCmdReceive.clear();
    const DeserializationError err=deserializeJson(jsonCmdReceive,message.message);
    if (err!=DeserializationError::Ok) { rocellOwnerRejected=true;return; }
    // Both direct and formerly deferred callback JSON now execute in the owner.
    if (!rocellOwnerFault()) jsonCmdReceiveHandler();
    jsonCmdReceive.clear();
  }
}

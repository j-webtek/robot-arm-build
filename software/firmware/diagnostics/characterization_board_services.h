// Include after existing diagnostic board globals. Opt-in adapter only; this
// file does not register routes, instantiate a controller or touch hardware.
#pragma once
#include "characterization_controller.h"
#include "park_reanchor_policy.h"
#include "air_typing_policy.h"
namespace rocell_diag {
// Reuse the exact seven-servo, raw-feedback acquisition used by the
// characterization path; no independent interpretation of servo registers.
struct FixedPairReanchorAcquisition {
  template<class Bus,class Clock,class Admission>
  static bool sample(Bus& bus,Clock& clock,ShoulderPreloadPose& pose,Admission& admission){
    return ShoulderPreloadCandidate::sample(bus,clock,pose,admission);
  }
};
}
template<class Evidence> struct RocellCharacterizationServices {
  Evidence& evidence;
  bool reserved=false;
  bool healthy(){return rocellHoldHealthy(nullptr);}
  bool memory_fits(size_t bytes,size_t reserve){
    return ESP.getFreeHeap()>=bytes+reserve&&ESP.getMaxAllocHeap()>=bytes;
  }
  bool reserve(){
    if(rocellShoulderReserved||rocellDiagnosticOwned||rocellPoseReserved||rocellHoldChallengeAttempted||
        rocellHoldConfigured||rocellRecoveryReserved||
        rocellPairRuntime.phase()!=rocell_diag::PairNetworkPhase::New||
        !healthy()||!rocellConfigurationBusInactive(nullptr))return false;
    rocellShoulderReserved=true;rocellDiagnosticOwned=true;reserved=true;return true;
  }
  bool owned(){return reserved&&rocellShoulderReserved&&rocellDiagnosticOwned;}
  bool reanchor_sample(rocell_diag::ShoulderPreloadPose& pose){
    auto admitted=[this](){return owned()&&healthy();};
    return rocell_diag::FixedPairReanchorAcquisition::sample(st,rocellConfiguredClock,pose,admitted);
  }
  bool reanchor_write(uint8_t first,uint8_t second,uint16_t a,uint16_t b,
                      uint16_t speed,uint8_t acceleration){
    if(!owned()||!healthy()||first!=12||second!=13||a!=2389||b!=1725||
       speed!=20||acceleration!=1||st.End!=0)return false;
    uint8_t ids[2]={first,second},acc[2]={acceleration,acceleration};
    int16_t targets[2]={int16_t(a),int16_t(b)};
    uint16_t speeds[2]={speed,speed};
    st.SyncWritePosEx(ids,2,targets,speeds,acc); // No acknowledgement or retry.
    return st.Error==0;
  }
  bool reanchor_evidence(const char* event,const rocell_diag::ShoulderPreloadPose&){
    // The owner retains each pose and event stage. This guard keeps a failed
    // or displaced owner from treating an evidence callback as successful.
    return owned()&&healthy()&&event!=nullptr;
  }
  bool park_step_sample(rocell_diag::ShoulderPreloadPose& pose){
    auto admitted=[this](){return owned()&&healthy();};
    return rocell_diag::FixedPairReanchorAcquisition::sample(st,rocellConfiguredClock,pose,admitted);
  }
  bool park_step_write(uint8_t first,uint8_t second,uint16_t a,uint16_t b,
                       uint16_t speed,uint8_t acceleration){
    const int progress=2389-int(a);
    if(!owned()||!healthy()||first!=12||second!=13||progress<12||progress>48||
       progress%12||b!=1725+progress||speed!=20||acceleration!=1||st.End!=0)
      return false;
    uint8_t ids[2]={first,second},acc[2]={acceleration,acceleration};
    int16_t targets[2]={int16_t(a),int16_t(b)};
    uint16_t speeds[2]={speed,speed};
    st.SyncWritePosEx(ids,2,targets,speeds,acc); // Broadcast, not an acknowledgement.
    return st.Error==0;
  }
  bool park_step_evidence(const char* event,const rocell_diag::ShoulderPreloadPose&){
    return owned()&&healthy()&&event!=nullptr;
  }
  bool park_return_sample(rocell_diag::ShoulderPreloadPose& pose){
    auto admitted=[this](){return owned()&&healthy();};
    return rocell_diag::FixedPairReanchorAcquisition::sample(st,rocellConfiguredClock,pose,admitted);
  }
  bool park_return_write(uint8_t first,uint8_t second,uint16_t a,uint16_t b,
                         uint16_t speed,uint8_t acceleration){
    // Bind the hardware adapter to the reviewed policy. Duplicating the r57
    // literals here caused r58 to reject its new target before the bus call.
    if(!owned()||!healthy()||first!=12||second!=13||
       a!=rocell_diag::ParkReanchorPolicy::target12||
       b!=rocell_diag::ParkReanchorPolicy::target13||
       speed!=20||acceleration!=1||st.End!=0)return false;
    uint8_t ids[2]={first,second},acc[2]={acceleration,acceleration};
    int16_t targets[2]={int16_t(a),int16_t(b)};
    uint16_t speeds[2]={speed,speed};
    st.SyncWritePosEx(ids,2,targets,speeds,acc); // Broadcast; no ack or retry.
    return st.Error==0;
  }
  bool park_return_evidence(const char* event,const rocell_diag::ShoulderPreloadPose&){
    return owned()&&healthy()&&event!=nullptr;
  }
  bool large_pose_lift_sample(rocell_diag::ShoulderPreloadPose& pose){
    auto admitted=[this](){return owned()&&healthy();};
    return rocell_diag::FixedPairReanchorAcquisition::sample(st,rocellConfiguredClock,pose,admitted);
  }
  bool large_pose_lift_write(uint8_t first,uint8_t second,uint8_t third,
      uint16_t a,uint16_t b,uint16_t c,uint16_t speed,uint8_t acceleration){
    if(!owned()||!healthy()||first!=12||second!=13||third!=15||
       a!=2348||b!=1766||c!=1654||speed!=20||acceleration!=1||st.End!=0)
      return false;
    uint8_t ids[3]={first,second,third},acc[3]={acceleration,acceleration,acceleration};
    int16_t targets[3]={int16_t(a),int16_t(b),int16_t(c)};
    uint16_t speeds[3]={speed,speed,speed};
    st.SyncWritePosEx(ids,3,targets,speeds,acc); // One broadcast; no retry.
    return st.Error==0;
  }
  bool large_pose_lift_evidence(const char* event,const rocell_diag::ShoulderPreloadPose&){
    return owned()&&healthy()&&event!=nullptr;
  }
  bool large_pose_relief_sample(rocell_diag::ShoulderPreloadPose& pose){
    auto admitted=[this](){return owned()&&healthy();};
    return rocell_diag::FixedPairReanchorAcquisition::sample(st,rocellConfiguredClock,pose,admitted);
  }
  bool large_pose_relief_write(uint8_t first,uint8_t second,uint16_t a,uint16_t b,
                               uint16_t speed,uint8_t acceleration){
    if(!owned()||!healthy()||first!=14||second!=15||a!=2842||b!=1719||
       speed!=20||acceleration!=1||st.End!=0)return false;
    uint8_t ids[2]={first,second},acc[2]={acceleration,acceleration};
    int16_t targets[2]={int16_t(a),int16_t(b)};
    uint16_t speeds[2]={speed,speed};
    st.SyncWritePosEx(ids,2,targets,speeds,acc); // One broadcast; no retry.
    return st.Error==0;
  }
  bool large_pose_relief_evidence(const char* event,const rocell_diag::ShoulderPreloadPose&){
    return owned()&&healthy()&&event!=nullptr;
  }
  bool air_typing_sample(rocell_diag::ShoulderPreloadPose& pose){
    auto admitted=[this](){return owned()&&healthy();};
    return rocell_diag::FixedPairReanchorAcquisition::sample(st,rocellConfiguredClock,pose,admitted);
  }
  bool air_typing_write(const uint16_t (&goals)[7],uint16_t speed,uint8_t acceleration){
    if(!owned()||!healthy()||speed!=20||acceleration!=1||st.End!=0)return false;
    bool reviewed=false;
    for(unsigned row=0;row<rocell_diag::AirTypingPolicy::legs;++row){
      bool same=true;
      for(unsigned i=0;i<7;++i)if(goals[i]!=rocell_diag::AirTypingPolicy::targets[row][i])same=false;
      if(same){reviewed=true;break;}
    }
    if(!reviewed)return false;
    uint8_t ids[7]={11,12,13,14,15,16,17};
    uint8_t acc[7]={1,1,1,1,1,1,1};
    int16_t targets[7];uint16_t speeds[7];
    for(unsigned i=0;i<7;++i){targets[i]=int16_t(goals[i]);speeds[i]=speed;}
    st.SyncWritePosEx(ids,7,targets,speeds,acc); // One broadcast; no retry.
    return st.Error==0;
  }
  bool air_typing_evidence(const char* event,const rocell_diag::ShoulderPreloadPose&){
    return owned()&&healthy()&&event!=nullptr;
  }
  auto& clock(){return rocellConfiguredClock;}
  auto& bus(){return st;}
  bool entropy(uint8_t* bytes,size_t size){esp_fill_random(bytes,size);return true;}
  bool load_key(uint8_t (&key)[32]){
    File file=LittleFS.open("/rocell-hold.key","r");rocell_diag::DiagnosticKeyMaterial material;
    bool ok=material.load(file);file.close();
    if(ok)ok=material.copy_to(key);material.clear();return ok;
  }
  bool boot(uint8_t (&bytes)[16]){
    if(strlen(rocellDiagnosticInstance)!=32)return false;
    for(unsigned i=0;i<32;++i){
      char c=rocellDiagnosticInstance[i];int n=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
      if(n<0)return false;
      if(i%2)bytes[i/2]|=n;else bytes[i/2]=n<<4;
    }
    return true;
  }
  bool retain(const char* event,unsigned leg,const rocell_diag::ShoulderPreloadPose& pose,
              const rocell_diag::CharacterizationResult* result){return evidence(event,leg,pose,result);}
  bool release_evidence(unsigned completed){return evidence.release_after_receipt(completed);}
};

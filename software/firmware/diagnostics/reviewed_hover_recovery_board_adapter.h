// r91-only seven-servo adapter. Construction does not access hardware.
#pragma once
#include "reviewed_hover_manifest.h"
#include "reviewed_hover_release_stamp.h"
#include "air_typing_policy.h"
#include <cstddef>
#include <cstdint>

namespace rocell_diag {
template<class ExistingServices,class Bus> class ReviewedHoverRecoveryBoardAdapter {
 public:
  static constexpr bool simulation_only=false;
  ReviewedHoverRecoveryBoardAdapter(ExistingServices& services,Bus& bus)
      :services_(services),bus_(bus){}
  bool healthy(){return services_.healthy();}
  bool memory_fits(size_t bytes,size_t reserve){
    return services_.memory_fits(bytes,reserve);
  }
  bool reserve(){return services_.reserve();}
  bool owned(){return services_.owned();}
  bool reviewed_hover_release_digest(uint8_t (&digest)[32]){
    uint8_t aggregate=0;
    for(unsigned i=0;i<32;++i){
      digest[i]=reviewed_hover_release_sha256[i];aggregate|=digest[i];
    }
    return aggregate!=0;
  }
  bool reviewed_hover_sample(ShoulderPreloadPose& pose){
    return owned()&&healthy()&&services_.air_typing_sample(pose);
  }
  bool reviewed_hover_evidence(const char* event,const ShoulderPreloadPose& pose){
    return owned()&&healthy()&&event&&services_.air_typing_evidence(event,pose);
  }
  bool reviewed_hover_write(const uint16_t (&goals)[7],uint16_t speed,uint8_t acceleration){
    if(!owned()||!healthy()||speed!=20||acceleration!=1||bus_.End!=0)return false;
    bool reviewed=false;
    for(unsigned row=ReviewedHoverManifest::A_CLEAR;
        row<=ReviewedHoverManifest::A_DOWN;++row){
      bool same=true;
      for(unsigned joint=0;joint<7;++joint)
        if(goals[joint]!=ReviewedHoverManifest::goals[row][joint])same=false;
      if(same){reviewed=true;break;}
    }
    if(!reviewed)return false;
    uint8_t ids[7]={11,12,13,14,15,16,17};
    uint8_t acc[7];int16_t targets[7];uint16_t speeds[7];
    for(unsigned joint=0;joint<7;++joint){
      acc[joint]=acceleration;targets[joint]=int16_t(goals[joint]);speeds[joint]=speed;
    }
    bus_.SyncWritePosEx(ids,7,targets,speeds,acc); // One broadcast; no retry.
    return bus_.Error==0;
  }
 private:
  ExistingServices& services_;
  Bus& bus_;
};
}

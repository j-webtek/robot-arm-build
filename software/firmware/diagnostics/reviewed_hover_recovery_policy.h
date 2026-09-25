// Offline fixed A_HOVER -> A_CLEAR -> A_HOVER -> A_DOWN -> A_HOVER -> A_CLEAR
// policy. Not registered in any firmware image or live route.
#pragma once
#include "air_typing_policy.h"
#include "reviewed_hover_manifest.h"
#include <cstdint>

namespace rocell_diag {
struct ReviewedHoverRecoveryPolicy : AirTypingPolicy {
  static constexpr unsigned legs = 5;
  static constexpr uint8_t poses[legs] = {
    ReviewedHoverManifest::A_CLEAR, ReviewedHoverManifest::A_HOVER,
    ReviewedHoverManifest::A_DOWN, ReviewedHoverManifest::A_HOVER,
    ReviewedHoverManifest::A_CLEAR,
  };
  uint8_t pose_ids[legs]{};
  unsigned count=0;
  bool configure(const uint8_t* ids,size_t size) {
    if(configured_)return false;
    if(!ids||size!=legs)return false;
    uint8_t prior=ReviewedHoverManifest::A_HOVER;
    for(unsigned n=0;n<legs;++n){
      if(ids[n]!=poses[n]||
         !ReviewedHoverManifest::selected_step(prior,ids[n]))return false;
      prior=ids[n];
    }
    constexpr uint16_t last_positions[7]={2041,2094,2020,2620,2199,2041,2047};
    for(unsigned i=0;i<7;++i){
      source_goals[i]=ReviewedHoverManifest::goals[ReviewedHoverManifest::A_HOVER][i];
      source_positions[i]=last_positions[i];
      target_goals[i]=ReviewedHoverManifest::goals[poses[0]][i];
    }
    // Last record is an admission envelope, not a substitute for fresh reads.
    // At the low side, the base position may be 12 counts from its goal.
    source_tolerance=6;
    for(unsigned n=0;n<legs;++n)pose_ids[n]=ids[n];
    count=legs;configured_=true;return true;
  }
  bool advance(const ShoulderPreloadPose& final,unsigned next){
    if(!configured_||next!=next_index_||next>=legs||
       !ShoulderCharacterizationPolicy::valid(final))return false;
    for(unsigned i=0;i<7;++i)
      if(final.goal[i]!=target_goals[i]||
         ShoulderCharacterizationPolicy::moving(final,i))return false;
    for(unsigned i=0;i<7;++i){
      source_goals[i]=final.goal[i];source_positions[i]=final.position[i];
      target_goals[i]=ReviewedHoverManifest::goals[poses[next]][i];
    }
    source_tolerance=1;++next_index_;return true;
  }
 private:
  bool configured_=false;
  unsigned next_index_=1;
};
}

// Offline controller-preparation owner. Capture/Reserve/Entropy must be trusted
// board services, never request-body adapters. No target or torque command API.
#pragma once
#include "characterization_session.h"
namespace rocell_diag {
// Trusted composition selection, not an arbitrary network target list.
enum class CharacterizationPattern { Legacy, Matched, Smoke, Matrix, Repeatability,
  ABControl, ABCandidate, ForwardRepeat, ReverseCandidate, ReverseControl,
  HeldoutCandidate, HeldoutControl, SecondHeldoutCandidate, SecondHeldoutControl,
  MappingBatch, SeparatedMappingBatch, FineLookupValidation, LocalIntervalCampaign,
  GhostPairTransitionCampaign, VisibleIntervalCampaign };
struct PreparedCharacterization {
  CharacterizationManifest manifest;
  uint8_t nonce[32]={},campaign[32]={},reference[32]={};
  uint64_t issued_us=0,expires_us=0;
};
class CharacterizationPrepare {
 public:
  template<class Reserve,class Capture,class Clock,class Entropy,class Crypto>
  bool prepare(Reserve& reserve,Capture& capture,Clock& clock,Entropy& entropy,Crypto& crypto,
               const uint16_t (&reviewed_bounds)[7][2],
               CharacterizationPattern pattern=CharacterizationPattern::Legacy){
    if(attempted_)return false;attempted_=true;
    if(pattern!=CharacterizationPattern::Legacy&&pattern!=CharacterizationPattern::Matched&&pattern!=CharacterizationPattern::Smoke&&pattern!=CharacterizationPattern::Matrix&&pattern!=CharacterizationPattern::Repeatability&&pattern!=CharacterizationPattern::ABControl&&pattern!=CharacterizationPattern::ABCandidate&&pattern!=CharacterizationPattern::ForwardRepeat&&pattern!=CharacterizationPattern::ReverseCandidate&&pattern!=CharacterizationPattern::ReverseControl&&pattern!=CharacterizationPattern::HeldoutCandidate&&pattern!=CharacterizationPattern::HeldoutControl&&pattern!=CharacterizationPattern::SecondHeldoutCandidate&&pattern!=CharacterizationPattern::SecondHeldoutControl&&pattern!=CharacterizationPattern::MappingBatch&&pattern!=CharacterizationPattern::SeparatedMappingBatch&&pattern!=CharacterizationPattern::FineLookupValidation&&pattern!=CharacterizationPattern::LocalIntervalCampaign&&pattern!=CharacterizationPattern::GhostPairTransitionCampaign&&pattern!=CharacterizationPattern::VisibleIntervalCampaign)return false;
    // Reservation is deliberately never refunded after a failed partial setup.
    if(!reserve())return false;
    if(!capture(poses_))return false;
    const auto now=clock.now_us();
    for(int n=0;n<3;++n){
      const auto& p=poses_[n];
      if(!ShoulderCharacterizationPolicy::valid(p)||p.finished_us>now||now-p.finished_us>1000000)return false;
      if(n&&(p.started_us<=poses_[n-1].finished_us||p.started_us-poses_[n-1].finished_us<100000))return false;
      for(int i=0;i<7;++i){
        if(reviewed_bounds[i][0]>reviewed_bounds[i][1]||reviewed_bounds[i][1]>4095||
            p.position[i]<reviewed_bounds[i][0]||p.position[i]>reviewed_bounds[i][1]||
            ShoulderCharacterizationPolicy::moving(p,i)||
            (p.feedback[i][0]|uint16_t(p.feedback[i][1])<<8)!=p.position[i]||
            p.goal[i]!=poses_[0].goal[i]||std::abs(int(p.position[i])-int(poses_[0].position[i]))>1)return false;
      }
    }
    const auto& current=poses_[2];
    if(int(current.goal[1])+current.goal[2]!=4114)return false;
    const bool ab=pattern==CharacterizationPattern::ABControl||pattern==CharacterizationPattern::ABCandidate;
    const bool repeat=pattern==CharacterizationPattern::ForwardRepeat;
    const bool reverse=pattern==CharacterizationPattern::ReverseCandidate||pattern==CharacterizationPattern::ReverseControl;
    const bool heldout=pattern==CharacterizationPattern::HeldoutCandidate||pattern==CharacterizationPattern::HeldoutControl;
    const bool second_heldout=pattern==CharacterizationPattern::SecondHeldoutCandidate||pattern==CharacterizationPattern::SecondHeldoutControl;
    const bool mapping_batch=pattern==CharacterizationPattern::MappingBatch;
    const bool separated_mapping=pattern==CharacterizationPattern::SeparatedMappingBatch;
    const bool fine_lookup=pattern==CharacterizationPattern::FineLookupValidation;
    const bool local_interval=pattern==CharacterizationPattern::LocalIntervalCampaign;
    const bool ghost_transition=pattern==CharacterizationPattern::GhostPairTransitionCampaign;
    const bool visible_interval=pattern==CharacterizationPattern::VisibleIntervalCampaign;
    // Absolute reviewed pilot, not a translated experiment. A control trial may
    // leave its goal at 2387; conditioning restores the same approach history.
    if(ab&&((current.goal[1]!=2389&&current.goal[1]!=2387)||
        std::abs(int(current.position[1])-2391)>1||std::abs(int(current.position[2])-1724)>1))return false;
    if((repeat||pattern==CharacterizationPattern::ReverseCandidate)&&
       (current.goal[1]!=2378||current.goal[2]!=1736||
        std::abs(int(current.position[1])-2387)>1||std::abs(int(current.position[2])-1730)>1))return false;
    if(pattern==CharacterizationPattern::ReverseControl&&
       (current.goal[1]!=2385||current.goal[2]!=1729||
        std::abs(int(current.position[1])-2387)>2||std::abs(int(current.position[2])-1728)>2))return false;
    if(pattern==CharacterizationPattern::HeldoutCandidate&&
       (current.goal[1]!=2386||current.goal[2]!=1728||
        std::abs(int(current.position[1])-2388)>1||std::abs(int(current.position[2])-1727)>1))return false;
    if(pattern==CharacterizationPattern::HeldoutControl&&
       (current.goal[1]!=2388||current.goal[2]!=1726||
        std::abs(int(current.position[1])-2390)>2||std::abs(int(current.position[2])-1725)>2))return false;
    if(pattern==CharacterizationPattern::SecondHeldoutCandidate&&
       (current.goal[1]!=2389||current.goal[2]!=1725||
        std::abs(int(current.position[1])-2390)>2||std::abs(int(current.position[2])-1724)>2))return false;
    if(pattern==CharacterizationPattern::SecondHeldoutControl&&
       (current.goal[1]!=2378||current.goal[2]!=1736||
        std::abs(int(current.position[1])-2388)>2||std::abs(int(current.position[2])-1729)>2))return false;
    if(mapping_batch&&(current.goal[1]!=2386||current.goal[2]!=1728||
        std::abs(int(current.position[1])-2391)>1||std::abs(int(current.position[2])-1724)>1))return false;
    if(separated_mapping&&(current.goal[1]!=2381||current.goal[2]!=1733||
        std::abs(int(current.position[1])-2387)>1||std::abs(int(current.position[2])-1728)>1))return false;
    if(fine_lookup&&(current.goal[1]!=2387||current.goal[2]!=1727||
        std::abs(int(current.position[1])-2389)>1||std::abs(int(current.position[2])-1726)>1))return false;
    if(local_interval&&(current.goal[1]!=2389||current.goal[2]!=1725||
        std::abs(int(current.position[1])-2391)>1||std::abs(int(current.position[2])-1724)>1))return false;
    if(ghost_transition&&(current.goal[1]!=2389||current.goal[2]!=1725||
        std::abs(int(current.position[1])-2391)>1||std::abs(int(current.position[2])-1724)>1))return false;
    if(visible_interval&&(current.goal[1]!=2413||current.goal[2]!=1701||
        std::abs(int(current.position[1])-2415)>1||std::abs(int(current.position[2])-1700)>1))return false;
    prepared_.manifest.legs=pattern==CharacterizationPattern::Smoke?1:
      repeat?4:heldout?2:second_heldout?(pattern==CharacterizationPattern::SecondHeldoutCandidate?3:4):
      (ab||reverse)?3:pattern==CharacterizationPattern::Repeatability?6:
      visible_interval?4:local_interval?11:12;
    memcpy(prepared_.manifest.bounds,reviewed_bounds,sizeof(reviewed_bounds));
    const int legacy[12]={-8,0,-16,0,-8,0,-16,0,-8,0,-16,0};
    const int matched[12]={-8,0,-16,-8,0,-8,-16,-8,0,-8,-16,-8};
    const int matrix[12]={-4,0,-8,0,-12,0,-4,0,-8,0,-12,0};
    const int repeatability[6]={-12,0,-12,0,-12,0};
    const int* offsets=pattern==CharacterizationPattern::Repeatability?repeatability:
      pattern==CharacterizationPattern::Matrix?matrix:
      pattern==CharacterizationPattern::Matched?matched:legacy;
    for(unsigned n=0;n<prepared_.manifest.legs;++n)for(int j=0;j<2;++j){
      int goal=int(current.goal[j+1])+(j?-offsets[n]:offsets[n]);
      if(ab){
        const int primary=n==0?2377:n==1?2389:pattern==CharacterizationPattern::ABControl?2387:2378;
        goal=j?4114-primary:primary;
      }
      if(repeat){const int primary[4]={2389,2377,2389,2378};goal=j?4114-primary[n]:primary[n];}
      if(reverse){const int primary=n==0?2389:n==1?2377:
          pattern==CharacterizationPattern::ReverseCandidate?2385:2386;
        goal=j?4114-primary:primary;}
      if(heldout){const int primary=n==0?2377:
          pattern==CharacterizationPattern::HeldoutCandidate?2388:2389;
        goal=j?4114-primary:primary;}
      if(second_heldout){
        const bool candidate=pattern==CharacterizationPattern::SecondHeldoutCandidate;
        const int primary=candidate?(n==0?2377:n==1?2389:2378):
          (n==0?2389:n==1?2377:n==2?2389:2386);
        goal=j?4114-primary:primary;}
      if(mapping_batch){
        const int primary[12]={2377,2389,2379,2387,2381,2389,2377,2385,2389,2383,2377,2388};
        goal=j?4114-primary[n]:primary[n];}
      if(separated_mapping){
        const int primary[12]={2389,2377,2385,2389,2383,2377,2388,2377,2381,2389,2377,2387};
        goal=j?4114-primary[n]:primary[n];}
      if(fine_lookup){
        const int primary[12]={2377,2385,2389,2377,2385,2389,2377,2388,2389,2377,2388,2389};
        goal=j?4114-primary[n]:primary[n];}
      if(local_interval){
        const int primary[11]={2377,2383,2389,2377,2385,2389,2377,2388,2389,2377,2389};
        goal=j?4114-primary[n]:primary[n];}
      if(ghost_transition){
        const int primary[12]={2377,2386,2388,2386,2388,2386,2377,2386,2388,2386,2388,2389};
        goal=j?4114-primary[n]:primary[n];}
      if(visible_interval){
        const int primary[4]={2401,2389,2401,2413};
        goal=j?4114-primary[n]:primary[n];}
      if(goal<reviewed_bounds[j+1][0]||goal>reviewed_bounds[j+1][1]||
          std::abs(goal-int(current.position[j+1]))>32)return false;
      // Smoke is one existing -8/+8 goal step, not an automatic return.
      // Reject a residual that would put its actual travel in the wrong direction.
      if(pattern==CharacterizationPattern::Smoke&&
          (j?goal-int(current.position[2]):int(current.position[1])-goal)<2)return false;
      prepared_.manifest.goals[n][j]=uint16_t(goal);
    }
    // Canonical capture reference: timings and complete raw evidence, no padding.
    size_t size=0;
    auto put=[&](uint64_t value,unsigned width){for(int i=int(width)-1;i>=0;--i)reference_bytes_[size++]=uint8_t(value>>(8*i));};
    for(const auto& p:poses_){put(p.started_us,8);put(p.finished_us,8);
      for(int i=0;i<7;++i){put(p.position[i],2);put(p.goal[i],2);put(p.torque[i],1);
        for(auto byte:p.feedback[i])put(byte,1);}}
    if(!crypto.sha256(reference_bytes_,size,prepared_.reference)||
        !entropy(prepared_.nonce,32)||!entropy(prepared_.campaign,32))return false;
    uint8_t nonce_any=0,campaign_any=0;
    for(int i=0;i<32;++i){nonce_any|=prepared_.nonce[i];campaign_any|=prepared_.campaign[i];}
    if(!nonce_any||!campaign_any||!memcmp(prepared_.nonce,prepared_.campaign,32))return false;
    prepared_.issued_us=clock.now_us();
    if(prepared_.issued_us<now||prepared_.issued_us-current.finished_us>1000000||prepared_.issued_us>INT64_MAX-30000000)return false;
    prepared_.expires_us=prepared_.issued_us+30000000;ready_=true;return true;
  }
  const PreparedCharacterization* result()const{return ready_?&prepared_:nullptr;}
  size_t copy_reference(uint8_t* output,size_t capacity)const{
    if(!ready_||!output||capacity<sizeof(reference_bytes_))return 0;
    memcpy(output,reference_bytes_,sizeof(reference_bytes_));return sizeof(reference_bytes_);
  }
 private:
  bool attempted_=false,ready_=false;PreparedCharacterization prepared_;
  ShoulderPreloadPose poses_[3];uint8_t reference_bytes_[468]={};
};
}

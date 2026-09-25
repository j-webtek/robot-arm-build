// Offline admission candidate. Expected manifest/capture identity must originate
// from controller-owned reviewed state, never the incoming request body.
#pragma once
#include "start_envelope.h"
#include "shoulder_characterization_owner.h"
namespace rocell_diag {
class CharacterizationAdmission {
 public:
  CharacterizationAdmission(const uint8_t (&key)[32],const uint8_t (&boot)[16],
      const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires,
      const uint8_t (&campaign)[32],const uint8_t (&reference)[32],
      const CharacterizationManifest& expected)
      :gate_(key,boot,nonce,issued,expires),manifest_(expected){
    auto put=[&](uint64_t value,unsigned width){
      for(int i=int(width)-1;i>=0;--i)canonical_[size_++]=uint8_t(value>>(8*i));
    };
    if(!expected.legs||expected.legs>12)return;
    const char domain[]="RCCADMIT01";for(char c:domain)put(uint8_t(c),1);
    for(auto b:campaign)put(b,1);for(auto b:reference)put(b,1);
    put(expected.legs,1);put(expected.maximum_us,8);
    for(auto& pair:expected.bounds)for(auto value:pair)put(value,2);
    for(unsigned i=0;i<expected.legs;++i)for(auto value:expected.goals[i])put(value,2);
    put(20,2);put(1,1); // Fixed speed/acceleration; no compensation.
    valid_=true;
  }
  template<class Crypto>
  bool start(const uint8_t* token,size_t length,uint64_t now,Crypto& crypto,
             ShoulderCharacterizationOwner& owner){
    AuthenticatedPlanView view;
    // Consume before comparison: a rejected or lost attempt is never reusable.
    if(!gate_.consume(token,length,now,crypto,view)||!valid_||
        view.length!=size_||memcmp(view.bytes,canonical_,size_))return false;
    return owner.begin(manifest_,now);
  }
 private:
  StartEnvelopeGate gate_;CharacterizationManifest manifest_;
  uint8_t canonical_[192]={};size_t size_=0;bool valid_=false;
};
}

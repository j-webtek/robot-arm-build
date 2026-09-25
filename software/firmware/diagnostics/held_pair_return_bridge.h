// Synchronous bridge for HeldElbowPairOwner::admit_return. Keep this object off
// the embedded task stack. Borrowed token/store/gate must outlive this call;
// top-level runtime owns their lifetimes and the bus throughout the transition.
#pragma once
#include "held_stored_return_admission.h"
namespace rocell_diag {
template<class Store,class Crypto,class Clock>
class HeldPairReturnBridge {
 public:
  HeldPairReturnBridge(HeldReturnAdmission& gate,const uint8_t* token,size_t length,
      Crypto& crypto,Clock& clock,const Store& store,const char* boot,
      const char* command,const char* session_hash,const char* plan_hash)
      :gate_(gate),token_(token),length_(length),crypto_(crypto),clock_(clock),store_(store){
    valid_=copy(boot_,boot)&&copy(command_,command)&&copy(session_,session_hash)&&copy(plan_,plan_hash);
  }
  HeldPairReturnBridge(const HeldPairReturnBridge&)=delete;
  HeldPairReturnBridge& operator=(const HeldPairReturnBridge&)=delete;
  bool consume(uint16_t original_anchor,const HeldElbowLegOwner& forward){
    if(attempted_)return false;attempted_=true;
    if(!valid_)return false;
    return admission_.consume(gate_,token_,length_,clock_.now_us(),crypto_,store_,
                              forward,boot_,command_,session_,plan_,original_anchor);
  }
 private:
  template<size_t N> static bool copy(char (&out)[N],const char* value){
    if(!value)return false;
    size_t n=0;while(n<N&&value[n])++n;
    if(!n||n==N)return false;memcpy(out,value,n+1);return true;
  }
  HeldReturnAdmission& gate_;const uint8_t* token_;size_t length_;
  Crypto& crypto_;Clock& clock_;const Store& store_;
  HeldStoredReturnAdmission admission_;
  char boot_[33]={},command_[129]={},session_[65]={},plan_[65]={};
  bool valid_=false,attempted_=false;
};
}

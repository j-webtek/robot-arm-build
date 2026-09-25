// Local capability issued only by the authenticated hold runtime. It carries a
// historical verified endpoint, not a substitute for fresh pair acquisition.
#pragma once
#include "hold_state_snapshot.h"
#include <string.h>
namespace rocell_diag {
template<class Library,class Clock,class Sink,class Crypto,bool Recovery,uint8_t RecoveryLimit> class HoldAuthenticatedRuntime;
class VerifiedHoldHandoff {
 public:
  VerifiedHoldHandoff()=default;
  VerifiedHoldHandoff(const VerifiedHoldHandoff&)=delete;
  VerifiedHoldHandoff& operator=(const VerifiedHoldHandoff&)=delete;
  const char* plan_hash()const{return valid_?plan_:nullptr;}
  const HoldStateSnapshot* consume(const char* boot,const char* plan,const char* policy){
    if(used_)return nullptr;used_=true;
    if(!valid_||!boot||!plan||!policy||strcmp(boot,boot_)||strcmp(plan,plan_)||strcmp(policy,policy_))return nullptr;
    return &endpoint_;
  }
 private:
  template<class Library,class Clock,class Sink,class Crypto,bool Recovery,uint8_t RecoveryLimit> friend class HoldAuthenticatedRuntime;
  bool seal(const HoldStateSnapshot& endpoint,const char* boot,const char* plan,const char* policy){
    if(valid_||used_||!endpoint.complete()||!boot||!plan||!policy||
       strlen(boot)!=32||strlen(plan)!=64||strlen(policy)!=64)return false;
    endpoint_=endpoint;memcpy(boot_,boot,33);memcpy(plan_,plan,65);memcpy(policy_,policy,65);
    valid_=true;return true;
  }
  HoldStateSnapshot endpoint_;char boot_[33]={},plan_[65]={},policy_[65]={};
  bool valid_=false,used_=false;
};
}

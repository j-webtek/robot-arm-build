// Initial pair authorization. No bus access; a verified same-boot hold and
// exclusive runtime ownership are additionally required before starting a pair.
#pragma once
#include "hold_plan_admission.h"
namespace rocell_diag {
class HeldPairPlanAdmission {
 public:
  HeldPairPlanAdmission(const uint8_t (&key)[32],const uint8_t (&boot)[16],
      const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires)
      :gate_(key,boot,nonce,issued,expires){hex(boot,16,boot_);}
  template<class Crypto> bool consume(const uint8_t* token,size_t length,uint64_t now,
      Crypto& crypto,const HoldInitializationPolicy& policy,const char* hold_plan_hash,
      const char* forward_command,const char* return_command,int offset,uint16_t tolerance){
    if(attempted_)return false;attempted_=true;
    if(!HoldInitializationOwner::policy_valid(policy)||!hash_valid(hold_plan_hash)||
       !valid_identity(forward_command)||!valid_identity(return_command)||
       !strcmp(forward_command,return_command)||tolerance>2||offset < -16||offset > 16||
       (offset>=-int(2*tolerance)&&offset<=int(2*tolerance)))return false;
    AuthenticatedPlanView view;
    if(!gate_.consume(token,length,now,crypto,view)||
       !hold_policy_json(policy,buffer_,sizeof(buffer_)))return false;
    uint8_t digest[32];
    if(!crypto.sha256(reinterpret_cast<const uint8_t*>(buffer_),strlen(buffer_),digest))return false;
    hex(digest,32,policy_hash_);
    JsonDocument doc;
    doc["boot_id"]=boot_;doc["forward_command_id"]=forward_command;
    doc["hold_plan_sha256"]=hold_plan_hash;doc["offset_counts"]=offset;
    doc["origin"]="DEVICE_CAPTURE";doc["policy_sha256"]=policy_hash_;
    doc["return_command_id"]=return_command;doc["schema"]="rocell.held_pair_plan.v1";
    doc["tolerance_counts"]=tolerance;
    if(!hold_json_finish(doc,buffer_,sizeof(buffer_))||strlen(buffer_)!=view.length||
       memcmp(buffer_,view.bytes,view.length)||!crypto.sha256(view.bytes,view.length,digest))return false;
    hex(digest,32,session_hash_);accepted_=true;return true;
  }
  const char* session_hash()const{return accepted_?session_hash_:nullptr;}
  const char* boot_id()const{return boot_;}
  const char* policy_hash()const{return accepted_?policy_hash_:nullptr;}
 private:
  static bool hash_valid(const char* value){
    if(!value||strlen(value)!=64)return false;
    for(size_t i=0;i<64;++i)if(!((value[i]>='0'&&value[i]<='9')||(value[i]>='a'&&value[i]<='f')))return false;
    return true;
  }
  static void hex(const uint8_t* bytes,size_t n,char* out){
    const char* digits="0123456789abcdef";
    for(size_t i=0;i<n;++i){out[2*i]=digits[bytes[i]>>4];out[2*i+1]=digits[bytes[i]&15];}
    out[2*n]=0;
  }
  StartEnvelopeGate gate_;bool attempted_=false,accepted_=false;
  char boot_[33]={},session_hash_[65]={},policy_hash_[65]={},buffer_[1536]={};
};
}

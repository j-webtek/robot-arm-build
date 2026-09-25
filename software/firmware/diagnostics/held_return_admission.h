// Single-use continuation authentication only. Does not poll or move a servo.
// Outer owner supplies locally retained forward plan/evidence/session identities
// and the original anchor, only after verified forward arrival. The signed
// export digest is a host assertion, not proof the controller inspected a disk.
#pragma once
#include "start_envelope.h"
#include "hold_evidence_json.h"
namespace rocell_diag {
class HeldReturnAdmission {
 public:
  HeldReturnAdmission(const uint8_t (&key)[32],const uint8_t (&boot)[16],
      const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires)
      :gate_(key,boot,nonce,issued,expires){
    const char* hex="0123456789abcdef";
    for(size_t i=0;i<16;++i){boot_[i*2]=hex[boot[i]>>4];boot_[i*2+1]=hex[boot[i]&15];}
  }
  template<class Crypto>
  bool consume(const uint8_t* token,size_t length,uint64_t now,Crypto& crypto,
      const char* session_hash,const char* forward_plan_hash,const char* evidence_hash,
      uint16_t original_anchor,bool forward_arrived){
    if(attempted_)return false;attempted_=true;
    if(!forward_arrived||original_anchor>4095||!hash_valid(session_hash)||
       !hash_valid(forward_plan_hash)||!hash_valid(evidence_hash))return false;
    AuthenticatedPlanView view;
    if(!gate_.consume(token,length,now,crypto,view)||view.length>=sizeof(buffer_))return false;
    JsonDocument input;
    if(deserializeJson(input,view.bytes,view.length)||!input.is<JsonObject>()||input.size()!=8)return false;
    const char* exported=input["export_sha256"].as<const char*>();
    if(!hash_valid(exported))return false;
    // Reconstruct canonical bytes; rejects extras, duplicate keys, altered
    // targets, wrong leg/session/boot and noncanonical encodings.
    JsonDocument expected;
    expected["boot_id"]=boot_;expected["evidence_sha256"]=evidence_hash;
    expected["export_sha256"]=exported;expected["forward_plan_sha256"]=forward_plan_hash;
    expected["origin"]="DEVICE_CAPTURE";expected["return_target_count"]=original_anchor;
    expected["schema"]="rocell.held_return_authorization.v1";
    expected["session_sha256"]=session_hash;
    if(!hold_json_finish(expected,buffer_,sizeof(buffer_))||strlen(buffer_)!=view.length||
       memcmp(buffer_,view.bytes,view.length))return false;
    memcpy(export_hash_,exported,65);accepted_=true;return true;
  }
  bool accepted()const{return accepted_;}
  const char* host_export_hash()const{return accepted_?export_hash_:nullptr;}
 private:
  static bool hash_valid(const char* value){
    if(!value||strlen(value)!=64)return false;
    for(size_t i=0;i<64;++i)if(!((value[i]>='0'&&value[i]<='9')||(value[i]>='a'&&value[i]<='f')))return false;
    return true;
  }
  StartEnvelopeGate gate_;bool attempted_=false,accepted_=false;
  char boot_[33]={},export_hash_[65]={},buffer_[1024]={};
};
}

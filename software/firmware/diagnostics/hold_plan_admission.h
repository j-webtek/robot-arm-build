// One-use authenticated match to a locally constructed reviewed hold plan.
// No reads/writes: caller still owns exclusive bus admission and export lifetime.
#pragma once
#include "start_envelope.h"
#include "hold_evidence_json.h"
namespace rocell_diag {
inline bool hold_policy_json(const HoldInitializationPolicy& p,char* out,size_t capacity){
  if(!out||!capacity)return false;out[0]=0;
  // Canonical sorted keys shared with the host. Enable is an explicit 0/1 value.
  JsonDocument doc;
  doc["acceleration"]=p.acceleration;doc["age_us"]=p.age_us;
  doc["baseline_gap_us"]=p.baseline_gap_us;doc["deadline_us"]=p.deadline_us;doc["drift"]=p.drift;
  auto joints=doc["joints"].to<JsonArray>();
  for(size_t i=0;i<7;++i){auto pair=joints.add<JsonArray>();pair.add(p.minimum[i]);pair.add(p.maximum[i]);}
  doc["maximum_gap_us"]=p.maximum_gap_us;doc["pair_us"]=p.pair_us;
  doc["permit_explicit_enable"]=p.permit_explicit_enable?1:0;
  doc["scan_us"]=p.scan_us;doc["schema"]="rocell.hold_policy.v1";
  doc["servo_id"]=14;doc["settle_us"]=p.settle_us;doc["speed"]=p.speed;
  return hold_json_finish(doc,out,capacity);
}
inline bool recovery_policy_json(const HoldInitializationPolicy& p,char* out,size_t capacity,uint8_t residual=5){
  if(residual!=5&&residual!=6)return false;
  if(!HoldInitializationOwner::policy_valid(p)||p.drift!=2||p.speed!=20||
     p.permit_explicit_enable||!hold_policy_json(p,out,capacity))return false;
  JsonDocument hold;if(deserializeJson(hold,out))return false;
  JsonDocument doc;doc["hold_policy"].set(hold.as<JsonVariantConst>());
  doc["initial_residual_counts"]=residual;
  doc["schema"]=residual==6?"rocell.six_count_recovery_policy.v1":"rocell.supported_recovery_policy.v1";
  return hold_json_finish(doc,out,capacity);
}
class HoldPlanAdmission {
 public:
  HoldPlanAdmission(const uint8_t (&key)[32],const uint8_t (&boot)[16],
      const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires)
      :gate_(key,boot,nonce,issued,expires){
    hex(boot,16,boot_);
  }
  template<class Crypto>
  bool consume(const uint8_t* token,size_t length,uint64_t now,Crypto& crypto,
               const HoldInitializationPolicy& reviewed,const char* reviewed_command,
               bool recovery=false,uint8_t residual=5){
    if(attempted_)return false;attempted_=true;
    AuthenticatedPlanView view;
    if(!gate_.consume(token,length,now,crypto,view)||!valid_identity(reviewed_command))return false;
    if((!recovery&&residual!=5)||!(recovery?recovery_policy_json(reviewed,scratch_,sizeof(scratch_),residual):
                  hold_policy_json(reviewed,scratch_,sizeof(scratch_))))return false;
    uint8_t digest[32]={};
    if(!crypto.sha256(reinterpret_cast<const uint8_t*>(scratch_),strlen(scratch_),digest))return false;
    hex(digest,32,policy_hash_);
    JsonDocument doc;
    doc["boot_id"]=boot_;doc["command_id"]=reviewed_command;
    doc["origin"]="DEVICE_CAPTURE";doc["policy_sha256"]=policy_hash_;
    doc["schema"]=recovery?(residual==6?"rocell.six_count_recovery_plan.v1":"rocell.supported_recovery_plan.v1"):"rocell.hold_plan.v1";
    if(!hold_json_finish(doc,scratch_,sizeof(scratch_))||strlen(scratch_)!=view.length||
       memcmp(scratch_,view.bytes,view.length))return false;
    if(!crypto.sha256(view.bytes,view.length,digest))return false;
    hex(digest,32,plan_hash_);accepted_=true;return true;
  }
  bool accepted()const{return accepted_;}
  const char* plan_hash()const{return accepted_?plan_hash_:nullptr;}
  const char* policy_hash()const{return accepted_?policy_hash_:nullptr;}
 private:
  static void hex(const uint8_t* bytes,size_t length,char* out){
    const char* digits="0123456789abcdef";
    for(size_t i=0;i<length;++i){out[2*i]=digits[bytes[i]>>4];out[2*i+1]=digits[bytes[i]&15];}
    out[2*length]=0;
  }
  StartEnvelopeGate gate_;bool attempted_=false,accepted_=false;
  char boot_[33]={},policy_hash_[65]={},plan_hash_[65]={},scratch_[1536]={};
};
}

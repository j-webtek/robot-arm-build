// Strict one-use parser for a separately provisioned hold-only configuration.
// No filesystem/network/servo calls. No default values on malformed input.
#pragma once
#include "strict_plan_json.h"
#include "hold_plan_admission.h"
namespace rocell_diag {
struct ControllerHoldConfig {
  HoldInitializationPolicy policy;
  uint16_t port=0;
  char command[129]={};
};
class ControllerHoldConfigParser {
 public:
  bool parse(const char* bytes,size_t length){
    if(used_)return false;used_=true;
    StrictPlanJson lexical;
    if(!bytes||!length||length>=sizeof(scratch_)||!lexical.check(bytes,length))return false;
    JsonDocument doc;
    if(deserializeJson(doc,bytes,length,DeserializationOption::NestingLimit(5)))return false;
    const auto root=doc.as<JsonObjectConst>();
    if(root.size()!=4||!text(root["schema"],"rocell.controller_hold.v1")||
       !root["command_id"].is<const char*>()||!valid_identity(root["command_id"].as<const char*>())||
       !integer(root["start_port"],1024,65535)||!root["hold_policy"].is<JsonObjectConst>())return false;
    const auto p=root["hold_policy"].as<JsonObjectConst>();
    if(p.size()!=14||!text(p["schema"],"rocell.hold_policy.v1")||!integer(p["servo_id"],14,14)||
       !integer(p["acceleration"],1,1)||!integer(p["speed"],1,40)||!integer(p["drift"],0,8)||
       !integer(p["permit_explicit_enable"],0,1)||!integer(p["age_us"],1,1000000)||
       !integer(p["baseline_gap_us"],1,1000000)||!integer(p["deadline_us"],1,10000000)||
       !integer(p["maximum_gap_us"],1,1000000)||!integer(p["pair_us"],1,100000)||
       !integer(p["scan_us"],1,1000000)||!integer(p["settle_us"],1,1000000)||
       !p["joints"].is<JsonArrayConst>()||p["joints"].size()!=7)return false;
    auto& policy=config_.policy;
    policy.acceleration=p["acceleration"].as<uint8_t>();policy.speed=p["speed"].as<uint16_t>();
    policy.drift=p["drift"].as<uint16_t>();policy.permit_explicit_enable=p["permit_explicit_enable"].as<unsigned>()==1;
    policy.age_us=p["age_us"].as<uint64_t>();policy.baseline_gap_us=p["baseline_gap_us"].as<uint64_t>();
    policy.deadline_us=p["deadline_us"].as<uint64_t>();policy.maximum_gap_us=p["maximum_gap_us"].as<uint64_t>();
    policy.pair_us=p["pair_us"].as<uint64_t>();policy.scan_us=p["scan_us"].as<uint64_t>();
    policy.settle_us=p["settle_us"].as<uint64_t>();
    for(size_t i=0;i<7;++i){const auto pair=p["joints"][i];
      if(!pair.is<JsonArrayConst>()||pair.size()!=2||!integer(pair[0],0,4095)||
         !integer(pair[1],pair[0].as<uint16_t>(),4095))return false;
      policy.minimum[i]=pair[0].as<uint16_t>();policy.maximum[i]=pair[1].as<uint16_t>();
    }
    if(!HoldInitializationOwner::policy_valid(policy))return false;
    config_.port=root["start_port"].as<uint16_t>();
    const char* command=root["command_id"].as<const char*>();memcpy(config_.command,command,strlen(command)+1);
    // Round-trip the decoded policy to reject unknown fields, floats, escapes,
    // whitespace and coercions even if the JSON library accepts them.
    if(!hold_policy_json(policy,scratch_,sizeof(scratch_)))return false;
    JsonDocument decoded;if(deserializeJson(decoded,scratch_))return false;
    JsonDocument expected;expected["command_id"]=config_.command;
    expected["hold_policy"].set(decoded.as<JsonVariantConst>());
    expected["schema"]="rocell.controller_hold.v1";expected["start_port"]=config_.port;
    if(!hold_json_finish(expected,scratch_,sizeof(scratch_))||strlen(scratch_)!=length||memcmp(scratch_,bytes,length))return false;
    valid_=true;return true;
  }
  const ControllerHoldConfig* get()const{return valid_?&config_:nullptr;}
 private:
  static bool text(JsonVariantConst value,const char* expected){return value.is<const char*>()&&!strcmp(value.as<const char*>(),expected);}
  static bool integer(JsonVariantConst value,uint64_t low,uint64_t high){return value.is<uint64_t>()&&value.as<uint64_t>()>=low&&value.as<uint64_t>()<=high;}
  bool used_=false,valid_=false;ControllerHoldConfig config_;char scratch_[2048]={};
};
}

// Explicit local policy, never inferred from a start request or test defaults.
// Parsing does not prove physical clearance and performs no filesystem/device I/O.
#pragma once
#include "start_plan_structure.h"
namespace rocell_diag {
struct ControllerDiagnosticConfig {
  char policy_id[129]={},conversion[129]={};
  uint16_t port=0,maximum_speed=0;uint8_t maximum_acceleration=0;
  double minimum_rad=0,maximum_rad=0;uint64_t challenge_lifetime_us=0;
  WholeArmBaselinePolicy whole={};
};
class ControllerDiagnosticConfigParser {
 public:
  bool parse(const char* bytes,size_t length,const char* expected_conversion){
    valid_=false;config_={};StrictPlanJson lexical;JsonDocument document;
    if(!valid_identity(expected_conversion) || length>4096 || !lexical.check(bytes,length) ||
       deserializeJson(document,bytes,length,DeserializationOption::NestingLimit(5)) || document.overflowed())return false;
    const auto root=document.as<JsonVariantConst>();
    static const char* const names[]={"schema","policy_id","conversion_version","start_port","challenge_lifetime_us","elbow_bounds","whole_arm_policy"};
    static const char* const bounds[]={"minimum_rad","maximum_rad","maximum_speed","maximum_acceleration"};
    static const char* const whole[]={"joints","tracking_tolerance","maximum_pair_us","maximum_scan_us","maximum_age_us"};
    const auto b=root["elbow_bounds"],w=root["whole_arm_policy"];
    if(!plan_fields(root,names,7)||!plan_fields(b,bounds,4)||!plan_fields(w,whole,5)||
       !plan_string(root["schema"],"rocell.controller_diagnostics.v1")||
       !plan_string(root["conversion_version"],expected_conversion)||
       !root["policy_id"].is<const char*>()||!valid_identity(root["policy_id"].as<const char*>())||
       !plan_integer(root["start_port"],1024,65535)||
       !plan_integer(root["challenge_lifetime_us"],1,30000000)||
       !plan_integer(b["maximum_speed"],1,65535)||!plan_integer(b["maximum_acceleration"],1,255)||
       !b["minimum_rad"].is<double>()||!b["maximum_rad"].is<double>())return false;
    const double low=b["minimum_rad"],high=b["maximum_rad"];
    if(!std::isfinite(low)||!std::isfinite(high)||low<0||low>high||high>3.141592653589793)return false;
    if(!plan_integer(w["tracking_tolerance"],0,16)||!plan_integer(w["maximum_pair_us"],1,1000000)||
       !plan_integer(w["maximum_scan_us"],1,7000000)||!plan_integer(w["maximum_age_us"],1,1000000)||
       !w["joints"].is<JsonArrayConst>()||w["joints"].size()!=7)return false;
    ControllerDiagnosticConfig candidate;
    for(size_t i=0;i<7;++i){const auto pair=w["joints"][i];
      if(!pair.is<JsonArrayConst>()||pair.size()!=2||!plan_integer(pair[0],0,4095)||
         !plan_integer(pair[1],pair[0].as<uint16_t>(),4095))return false;
      candidate.whole.joints[i]={pair[0].as<uint16_t>(),pair[1].as<uint16_t>()};
    }
    candidate.whole.tracking_tolerance=w["tracking_tolerance"];
    candidate.whole.maximum_pair_us=w["maximum_pair_us"];
    candidate.whole.maximum_scan_us=w["maximum_scan_us"];
    candidate.whole.maximum_age_us=w["maximum_age_us"];
    const char* id=root["policy_id"];
    memcpy(candidate.policy_id,id,strlen(id)+1);
    memcpy(candidate.conversion,expected_conversion,strlen(expected_conversion)+1);
    candidate.port=root["start_port"];candidate.challenge_lifetime_us=root["challenge_lifetime_us"];
    candidate.minimum_rad=low;candidate.maximum_rad=high;
    candidate.maximum_speed=b["maximum_speed"];candidate.maximum_acceleration=b["maximum_acceleration"];
    config_=candidate;valid_=true;return true;
  }
  const ControllerDiagnosticConfig* get() const{return valid_?&config_:nullptr;}
 private:
  bool valid_=false;ControllerDiagnosticConfig config_;
};

// Read-only, exact-size key loading. No creation, repair, logging or fallback.
// The caller opens a separately provisioned binary file and never exports it.
class DiagnosticKeyMaterial {
 public:
  DiagnosticKeyMaterial()=default;
  ~DiagnosticKeyMaterial(){clear();}
  DiagnosticKeyMaterial(const DiagnosticKeyMaterial&)=delete;
  DiagnosticKeyMaterial& operator=(const DiagnosticKeyMaterial&)=delete;
  template<class File> bool load(File& file){
    clear();
    if(!file || file.size()!=32){file.close();return false;}
    const auto count=file.read(key_,32);file.close();
    uint8_t nonzero=0,fixture_difference=0;
    for(size_t i=0;i<32;++i){nonzero|=key_[i];fixture_difference|=key_[i]^static_cast<uint8_t>(i);}
    if(count!=32 || !nonzero || !fixture_difference){clear();return false;}
    valid_=true;return true;
  }
  bool copy_to(uint8_t (&output)[32]) const{
    memset(output,0,32);if(!valid_)return false;memcpy(output,key_,32);return true;
  }
  void clear(){volatile uint8_t* p=key_;for(size_t i=0;i<32;++i)p[i]=0;valid_=false;}
 private:
  uint8_t key_[32]={};bool valid_=false;
};
}

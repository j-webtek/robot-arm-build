// Explicit separately provisioned startup policy; normal policy is not upgraded.
#pragma once
#include "controller_diagnostic_config.h"
#include "startup_position_baseline.h"
namespace rocell_diag {
struct ControllerStartupConfig {
  ControllerDiagnosticConfig normal;
  StartupPositionPolicy startup={};uint8_t reviewed_mode=0;
};
class ControllerStartupConfigParser {
 public:
  bool parse(const char* bytes,size_t length,const char* conversion){
    valid_=false;config_={};StrictPlanJson lexical;JsonDocument doc;
    if(!bytes||length>4096||!lexical.check(bytes,length)||
       deserializeJson(doc,bytes,length,DeserializationOption::NestingLimit(6))||doc.overflowed())return false;
    const auto root=doc.as<JsonVariantConst>();
    static const char* const fields[]={"schema","controller_policy","startup_policy"};
    static const char* const startup_fields[]={"drift_tolerance","joints","maximum_age_us","maximum_pair_us",
      "maximum_scan_us","maximum_wait_us","minimum_separation_us","mode","policy_id","reviewed_mode"};
    const auto p=root["startup_policy"];
    if(!plan_fields(root,fields,3)||!plan_string(root["schema"],"rocell.controller_startup.v1")||
       !plan_fields(p,startup_fields,10)||!plan_string(p["mode"],"ZERO_GOAL_TWO_SCAN"))return false;
    // Reuse strict existing controller configuration validation without changing
    // its schema or making a normal configuration authorize startup implicitly.
    const auto size=measureJson(root["controller_policy"]);
    if(!size||size>=sizeof(normal_bytes_))return false;
    serializeJson(root["controller_policy"],normal_bytes_,sizeof(normal_bytes_));
    ControllerDiagnosticConfigParser normal;
    if(!normal.parse(normal_bytes_,size,conversion))return false;
    ControllerStartupConfig candidate;candidate.normal=*normal.get();
    if(!plan_string(p["policy_id"],candidate.normal.policy_id)||
       !plan_integer(p["reviewed_mode"],0,255)||!plan_integer(p["drift_tolerance"],0,16)||
       !plan_integer(p["minimum_separation_us"],1,5000000)||!plan_integer(p["maximum_wait_us"],1,5000000)||
       !plan_integer(p["maximum_pair_us"],1,1000000)||!plan_integer(p["maximum_scan_us"],1,7000000)||
       !plan_integer(p["maximum_age_us"],1,1000000)||
       !p["joints"].is<JsonArrayConst>()||p["joints"].size()!=7)return false;
    auto& s=candidate.startup;
    s.minimum_separation_us=p["minimum_separation_us"];s.maximum_wait_us=p["maximum_wait_us"];
    if(s.minimum_separation_us>s.maximum_wait_us||
       s.minimum_separation_us>=candidate.normal.challenge_lifetime_us)return false;
    s.maximum_pair_us=p["maximum_pair_us"];s.maximum_scan_us=p["maximum_scan_us"];
    s.maximum_age_us=p["maximum_age_us"];s.drift_tolerance=p["drift_tolerance"];
    candidate.reviewed_mode=p["reviewed_mode"];
    for(size_t i=0;i<7;++i){const auto w=p["joints"][i];const auto& n=candidate.normal.whole.joints[i];
      if(!w.is<JsonArrayConst>()||w.size()!=2||!plan_integer(w[0],n.minimum,n.minimum)||
         !plan_integer(w[1],n.maximum,n.maximum))return false;
      s.joints[i]=n;
    }
    config_=candidate;valid_=true;return true;
  }
  const ControllerStartupConfig* get()const{return valid_?&config_:nullptr;}
 private:
  // Runtime owns this parser for its lifetime; keep the 4 KiB scratch buffer off
  // the ESP32 loop-task stack. No policy/key bytes are logged or exported here.
  char normal_bytes_[4096]={};
  bool valid_=false;ControllerStartupConfig config_;
};
}

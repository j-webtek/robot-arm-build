// Native structural/limit validation followed by bind_payload(). Both stages
// are required; neither authenticates ingress or establishes physical admission.
#pragma once
#include <ArduinoJson.h>
#include <cmath>
#include "strict_plan_json.h"
#include "servo_evidence_json.h"
#include "diagnostic_receipt.h"
#include "payload_base64.h"
#include "whole_arm_baseline.h"
namespace rocell_diag {
struct BoundStartRequest {
  bool has_whole_arm=false;WholeArmBaselinePolicy whole_arm={};
  char boot[129]={},command[129]={},payload[257]={};size_t payload_length=0;
  uint16_t wire_count=0,desired_count=0,samples=0;
  uint64_t interval_us=0,pair_us=0,baseline_pair_us=0,baseline_age_us=0;
  uint16_t maximum_delta=0,settled_tolerance=0;
};
inline bool plan_fields(JsonVariantConst value,const char* const* names,size_t count) {
  if(!value.is<JsonObjectConst>() || value.size()!=count)return false;
  for(size_t i=0;i<count;++i)if(value[names[i]].isNull())return false;
  return true;
}
inline bool plan_integer(JsonVariantConst value,uint64_t low,uint64_t high) {
  return value.is<uint64_t>() && value.as<uint64_t>()>=low && value.as<uint64_t>()<=high;
}
inline bool plan_string(JsonVariantConst value,const char* expected) {
  return expected && value.is<const char*>() && strcmp(value.as<const char*>(),expected)==0;
}
class StartPlanStructure {
 public:
  bool parse(const char* bytes,size_t length,const char* boot,const char* conversion,
             const WholeArmBaselinePolicy* approved=nullptr) {
    parsed_=false;bound_=false;whole_=false;payload_length_=0;document_.clear();
    StrictPlanJson lexical;
    if(!valid_identity(boot)||!valid_identity(conversion)||!lexical.check(bytes,length) ||
        deserializeJson(document_,bytes,length,DeserializationOption::NestingLimit(5)) || document_.overflowed())return false;
    const JsonVariantConst doc=document_.as<JsonVariantConst>();
    static const char* const root[]={"baseline_policy","command","origin","policy","schedule","schema","sent_base64"};
    static const char* const root3[]={"baseline_policy","command","origin","policy","schedule","schema","sent_base64","whole_arm_policy"};
    static const char* const command[]={"angle_units","boot_id","command_id","conversion_version","desired_count","desired_rad","joint","payload","payload_sha256","position_units","servo_id","wire_count","wire_rad"};
    static const char* const payload[]={"T","acc","joint","rad","spd"};
    static const char* const policy[]={"maximum_gap_us","maximum_pair_us","settle_us","tolerance_counts"};
    static const char* const schedule[]={"maximum_lateness_us","maximum_pair_us","sample_count","sample_interval_us"};
    static const char* const baseline[]={"maximum_age_us","maximum_delta_counts","maximum_pair_us","settled_tolerance_counts"};
    const auto c=doc["command"],p=c["payload"],s=doc["schedule"],b=doc["baseline_policy"],q=doc["policy"];
    whole_=plan_string(doc["schema"],"rocell.session_plan.v3");
    if(!(whole_?plan_fields(doc,root3,8):plan_fields(doc,root,7))||!plan_fields(c,command,13)||!plan_fields(p,payload,5)||
       !plan_fields(q,policy,4)||!plan_fields(s,schedule,4)||!plan_fields(b,baseline,4))return false;
    if((!whole_ && !plan_string(doc["schema"],"rocell.session_plan.v2")) || !plan_string(doc["origin"],"DEVICE_CAPTURE") ||
       !plan_string(c["boot_id"],boot)||!plan_string(c["conversion_version"],conversion)||
       !plan_string(c["angle_units"],"rad")||!plan_string(c["position_units"],"count")||
       !c["command_id"].is<const char*>()||!valid_identity(c["command_id"].as<const char*>()))return false;
    if(!plan_integer(c["joint"],3,3)||!plan_integer(c["servo_id"],14,14)||
       !plan_integer(c["desired_count"],1024,3071)||!plan_integer(c["wire_count"],1024,3071)||
       !plan_integer(p["T"],101,101)||!plan_integer(p["joint"],3,3)||
       !plan_integer(p["spd"],1,65535)||!plan_integer(p["acc"],1,255))return false;
    for(const char* key:{"desired_rad","wire_rad"}) {
      if(!c[key].is<double>())return false;double angle=c[key].as<double>();
      if(!std::isfinite(angle)||angle<0 || angle>3.141592653589793)return false;
    }
    if(!p["rad"].is<double>()||p["rad"].as<double>()!=c["wire_rad"].as<double>())return false;
    if(!plan_integer(s["sample_count"],1,10)||!plan_integer(s["sample_interval_us"],1000,60000000)||
       !plan_integer(s["maximum_lateness_us"],1000,60000000)||!plan_integer(s["maximum_pair_us"],1,60000000)||
       s["maximum_lateness_us"].as<uint64_t>()!=s["sample_interval_us"].as<uint64_t>()||
       s["maximum_pair_us"].as<uint64_t>()>s["sample_interval_us"].as<uint64_t>())return false;
    if(!plan_integer(q["tolerance_counts"],0,100)||!plan_integer(q["settle_us"],1,INT64_MAX)||
       !plan_integer(q["maximum_gap_us"],1,INT64_MAX)||!plan_integer(q["maximum_pair_us"],1,60000000)||
       q["maximum_pair_us"].as<uint64_t>()!=s["maximum_pair_us"].as<uint64_t>())return false;
    if(!plan_integer(b["maximum_age_us"],1,1000000)||!plan_integer(b["maximum_pair_us"],1,1000000)||
       !plan_integer(b["maximum_delta_counts"],1,64)||!plan_integer(b["settled_tolerance_counts"],0,16))return false;
    if(!c["payload_sha256"].is<const char*>()||!doc["sent_base64"].is<const char*>())return false;
    const char* hash=c["payload_sha256"];
    if(strlen(hash)!=64)return false;
    for(size_t i=0;i<64;++i)if(!((hash[i]>='0'&&hash[i]<='9')||(hash[i]>='a'&&hash[i]<='f')))return false;
    const char* sent=doc["sent_base64"];size_t n=strlen(sent);
    if(n<4 || n>344 || n%4)return false;
    if(whole_) {
      static const char* const names[]={"joints","tracking_tolerance","maximum_pair_us","maximum_scan_us","maximum_age_us"};
      const auto w=doc["whole_arm_policy"];
      if(!approved || !plan_fields(w,names,5)||!plan_integer(s["sample_count"],1,8)||
         !plan_integer(w["tracking_tolerance"],0,16)||!plan_integer(w["maximum_pair_us"],1,1000000)||
         !plan_integer(w["maximum_scan_us"],1,7000000)||!plan_integer(w["maximum_age_us"],1,1000000)||
         !w["joints"].is<JsonArrayConst>()||w["joints"].size()!=7)return false;
      if(w["tracking_tolerance"].as<uint16_t>()!=approved->tracking_tolerance ||
         w["maximum_pair_us"].as<uint64_t>()!=approved->maximum_pair_us ||
         w["maximum_scan_us"].as<uint64_t>()!=approved->maximum_scan_us ||
         w["maximum_age_us"].as<uint64_t>()!=approved->maximum_age_us)return false;
      for(size_t i=0;i<7;++i) {
        auto window=w["joints"][i];
        if(!window.is<JsonArrayConst>()||window.size()!=2||!plan_integer(window[0],0,4095)||
           !plan_integer(window[1],window[0].as<uint16_t>(),4095)||
           window[0].as<uint16_t>()!=approved->joints[i].minimum ||
           window[1].as<uint16_t>()!=approved->joints[i].maximum)return false;
      }
      whole_policy_=*approved;
    }
    // Retain exact sorted payload-object bytes, without float reserialization.
    // Lexical and exact-field checks above ensure a unique, flat numeric object.
    const char marker[]="\"payload\":";
    for(size_t i=0;i+sizeof(marker)-1<length;++i) {
      if(memcmp(bytes+i,marker,sizeof(marker)-1))continue;
      const size_t start=i+sizeof(marker)-1;size_t end=start;
      while(end<length && bytes[end]!='}')++end;
      if(end==length || end-start+1>256)return false;
      payload_length_=end-start+1;memcpy(payload_,bytes+start,payload_length_);break;
    }
    parsed_=payload_length_>0;return parsed_;
  }
  // Converter must be the reviewed no-write reference adapter, NOT a live
  // admission/write callback. Hash/receipt checks complete before conversion.
  template<class Crypto,class Converter>
  bool bind_payload(Crypto& crypto,Converter& converter) {
    if(!parsed_)return false;parsed_=false;bound_=false;
    const auto c=document_["command"].as<JsonVariantConst>();
    uint8_t digest[32]={};
    if(!crypto.sha256(reinterpret_cast<const uint8_t*>(payload_),payload_length_,digest))return false;
    const char* expected=c["payload_sha256"];
    static const char hex[]="0123456789abcdef";
    for(size_t i=0;i<32;++i)if(expected[2*i]!=hex[digest[i]>>4] || expected[2*i+1]!=hex[digest[i]&15])return false;
    size_t length=0;
    if(!decode_payload_base64(document_["sent_base64"].as<const char*>(),original_,length))return false;
    DiagnosticReceipt receipt;
    if(!receipt.accept(c["boot_id"],c["command_id"],original_,length,0) ||
       receipt.received_radians()!=c["wire_rad"].as<double>() ||
       receipt.speed()!=c["payload"]["spd"].as<uint16_t>() ||
       receipt.acceleration()!=c["payload"]["acc"].as<uint8_t>())return false;
    uint16_t wire=0,desired=0;
    if(!converter.admit_and_convert(receipt.received_radians(),receipt.speed(),receipt.acceleration(),wire)||
       wire!=c["wire_count"].as<uint16_t>() ||
       !converter.admit_and_convert(c["desired_rad"].as<double>(),receipt.speed(),receipt.acceleration(),desired)||
       desired!=c["desired_count"].as<uint16_t>())return false;
    original_length_=length;bound_=true;return true;
  }
  // Exact owned bytes are available only after full binding. They still carry
  // no physical admission; this class never accesses a servo or dispatches.
  const char* original_payload() const {return bound_?original_:nullptr;}
  size_t original_length() const {return bound_?original_length_:0;}
  bool copy_bound_request(BoundStartRequest& request) const {
    request={};if(!bound_)return false;
    request.has_whole_arm=whole_;if(whole_)request.whole_arm=whole_policy_;
    const auto c=document_["command"],s=document_["schedule"],b=document_["baseline_policy"];
    const char* boot=c["boot_id"];const char* command=c["command_id"];
    memcpy(request.boot,boot,strlen(boot)+1);
    memcpy(request.command,command,strlen(command)+1);
    memcpy(request.payload,original_,original_length_+1);request.payload_length=original_length_;
    request.wire_count=c["wire_count"];request.desired_count=c["desired_count"];
    request.samples=s["sample_count"];request.interval_us=s["sample_interval_us"];request.pair_us=s["maximum_pair_us"];
    request.baseline_pair_us=b["maximum_pair_us"];request.baseline_age_us=b["maximum_age_us"];
    request.maximum_delta=b["maximum_delta_counts"];request.settled_tolerance=b["settled_tolerance_counts"];
    return true;
  }
 private:
  JsonDocument document_;
  bool parsed_=false,bound_=false;
  bool whole_=false;WholeArmBaselinePolicy whole_policy_={};
  char payload_[256]={},original_[257]={};size_t payload_length_=0,original_length_=0;
};
}

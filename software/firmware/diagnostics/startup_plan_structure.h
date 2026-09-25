// Distinct startup wrapper; never accepted as a normal StartPlanStructure input.
// Authentication precedes parsing. Parsing/binding still authorizes no movement.
#pragma once
#include "start_plan_structure.h"
#include "startup_position_baseline.h"
namespace rocell_diag {
class StartupPlanStructure {
 public:
  bool parse(const char* bytes,size_t length,const char* boot,const char* conversion,
      const char* policy_id,const StartupPositionPolicy& approved,uint8_t mode,
      const WholeArmBaselinePolicy& normal_policy){
    parsed_=false;bound_=false;
    static const char prefix[]="{\"schema\":\"rocell.startup_session_plan.v1\",\"session_plan_base64\":\"";
    static const char middle[]="\",\"startup_policy\":";
    if(!bytes||length>16384||length<sizeof(prefix)+sizeof(middle)||
       memcmp(bytes,prefix,sizeof(prefix)-1)||bytes[length-1]!='}'||!valid_identity(policy_id))return false;
    size_t end=sizeof(prefix)-1;
    while(end<length && bytes[end]!='"')++end;
    if(end+sizeof(middle)-1>=length||memcmp(bytes+end,middle,sizeof(middle)-1))return false;
    const size_t start=end+sizeof(middle)-1;
    StrictPlanJson lexical;JsonDocument policy;
    if(!lexical.check(bytes+start,length-start-1)||
       deserializeJson(policy,bytes+start,length-start-1,DeserializationOption::NestingLimit(4)))return false;
    const auto p=policy.as<JsonVariantConst>();
    static const char* const fields[]={"drift_tolerance","joints","maximum_age_us","maximum_pair_us",
      "maximum_scan_us","maximum_wait_us","minimum_separation_us","mode","policy_id","reviewed_mode"};
    if(!plan_fields(p,fields,10)||!plan_string(p["mode"],"ZERO_GOAL_TWO_SCAN")||
       !plan_string(p["policy_id"],policy_id)||!plan_integer(p["reviewed_mode"],mode,mode)||
       !plan_integer(p["drift_tolerance"],0,16)||p["drift_tolerance"].as<uint16_t>()!=approved.drift_tolerance||
       !equal_limit(p["minimum_separation_us"],approved.minimum_separation_us,5000000)||
       !equal_limit(p["maximum_wait_us"],approved.maximum_wait_us,5000000)||
       approved.minimum_separation_us>approved.maximum_wait_us||
       !equal_limit(p["maximum_age_us"],approved.maximum_age_us,1000000)||
       !equal_limit(p["maximum_pair_us"],approved.maximum_pair_us,1000000)||
       !equal_limit(p["maximum_scan_us"],approved.maximum_scan_us,7000000)||
       !p["joints"].is<JsonArrayConst>()||p["joints"].size()!=7)return false;
    for(size_t i=0;i<7;++i){const auto w=p["joints"][i];const auto& a=approved.joints[i];
      if(a.minimum>a.maximum||a.maximum>4095||a.minimum!=normal_policy.joints[i].minimum||
         a.maximum!=normal_policy.joints[i].maximum||!w.is<JsonArrayConst>()||w.size()!=2||
         !plan_integer(w[0],a.minimum,a.minimum)||!plan_integer(w[1],a.maximum,a.maximum))return false;
    }
    size_t decoded=0;
    if(!decode(bytes+sizeof(prefix)-1,end-(sizeof(prefix)-1),decoded)||
       !normal_.parse(inner_,decoded,boot,conversion,&normal_policy))return false;
    // StartPlanStructure also accepts v2, but startup requires explicit v3.
    JsonDocument doc;
    if(deserializeJson(doc,inner_,decoded)||!plan_string(doc["schema"],"rocell.session_plan.v3")||
       !plan_integer(doc["schedule"]["sample_count"],1,6))return false;
    parsed_=true;return true;
  }
  template<class Crypto,class Converter>
  bool bind_payload(Crypto& crypto,Converter& converter){
    if(!parsed_)return false;parsed_=false;bound_=normal_.bind_payload(crypto,converter);return bound_;
  }
  bool copy_bound_request(BoundStartRequest& request)const{return bound_&&normal_.copy_bound_request(request);}
 private:
  static bool equal_limit(JsonVariantConst value,uint64_t expected,uint64_t maximum){
    return expected&&expected<=maximum&&plan_integer(value,expected,expected);
  }
  bool decode(const char* text,size_t size,size_t& written){
    written=0;if(!size||size%4||size>16384)return false;
    for(size_t i=0;i<size;i+=4){
      const int a=payload_base64_digit(text[i]),b=payload_base64_digit(text[i+1]);
      const bool p2=text[i+2]=='=',p3=text[i+3]=='=';
      const int c=p2?0:payload_base64_digit(text[i+2]),d=p3?0:payload_base64_digit(text[i+3]);
      if(a<0||b<0||c<0||d<0||(p2&&!p3)||((p2||p3)&&i+4!=size)||
         (p2&&(b&15))||(!p2&&p3&&(c&3)))return false;
      const size_t count=p2?1:p3?2:3;if(written+count>=sizeof(inner_))return false;
      inner_[written++]=static_cast<char>((a<<2)|(b>>4));
      if(count>1)inner_[written++]=static_cast<char>((b<<4)|(c>>2));
      if(count>2)inner_[written++]=static_cast<char>((c<<6)|d);
    }
    inner_[written]=0;return true;
  }
  char inner_[16385]={};StartPlanStructure normal_;bool parsed_=false,bound_=false;
};
}

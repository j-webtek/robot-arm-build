// Canonical, bounded local pair settings. Reject duplicates/coercion before any
// key read or hold retirement. No configuration defaults or hardware effects.
#pragma once
#include "strict_plan_json.h"
#include "hold_plan_admission.h"
namespace rocell_diag {
class ControllerPairConfigParser {
 public:
  bool parse(const char* bytes,size_t length){
    if(used_)return false;used_=true;
    StrictPlanJson lexical;
    if(!bytes||!length||length>1024||!lexical.check(bytes,length))return false;
    JsonDocument doc;
    if(deserializeJson(doc,bytes,length,DeserializationOption::NestingLimit(2))||
       !doc.is<JsonObject>()||doc.size()!=5||
       !doc["schema"].is<const char*>()||strcmp(doc["schema"],"rocell.controller_pair.v1")||
       !doc["forward_command_id"].is<const char*>()||!doc["return_command_id"].is<const char*>()||
       !doc["offset_counts"].is<int>()||!doc["tolerance_counts"].is<int>())return false;
    const char* forward=doc["forward_command_id"],*reverse=doc["return_command_id"];
    const int offset=doc["offset_counts"],tolerance=doc["tolerance_counts"];
    if(!valid_identity(forward)||!valid_identity(reverse)||!strcmp(forward,reverse)||
       offset<-16||offset>16||tolerance<0||tolerance>2||
       (offset>=-2*tolerance&&offset<=2*tolerance))return false;
    JsonDocument expected;expected["forward_command_id"]=forward;expected["offset_counts"]=offset;
    expected["return_command_id"]=reverse;expected["schema"]="rocell.controller_pair.v1";
    expected["tolerance_counts"]=tolerance;
    if(!hold_json_finish(expected,canonical_,sizeof(canonical_))||strlen(canonical_)!=length||
       memcmp(canonical_,bytes,length))return false;
    memcpy(forward_,forward,strlen(forward)+1);memcpy(reverse_,reverse,strlen(reverse)+1);
    offset_=offset;tolerance_=uint8_t(tolerance);valid_=true;return true;
  }
  const char* forward()const{return valid_?forward_:nullptr;}
  const char* reverse()const{return valid_?reverse_:nullptr;}
  int offset()const{return offset_;}
  uint8_t tolerance()const{return tolerance_;}
 private:
  bool used_=false,valid_=false;char forward_[129]={},reverse_[129]={};
  char canonical_[1025]={}; // Part of caller-owned scratch, not nested task stack.
  int offset_=0;uint8_t tolerance_=0;
};
}

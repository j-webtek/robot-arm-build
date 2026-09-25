#pragma once
#include "baseline_only_scan.h"
#include "whole_arm_baseline_json.h"
namespace rocell_diag {
inline bool baseline_only_json(const BaselineOnlyScan& scan,const char* boot,
                              const char* scan_id,char* output,size_t capacity) {
  if(!output||!capacity)return false;output[0]=0;
  if(!valid_identity(boot)||!valid_identity(scan_id))return false;
  JsonDocument doc;
  doc["schema"]="rocell.baseline_only.v1";doc["boot_id"]=boot;doc["scan_id"]=scan_id;
  doc["profile_id"]="waveshare-sms-sts-reference-b8b377642b3e";
  doc["byte_order"]="little";doc["complete"]=scan.complete();doc["reason"]=scan.reason();
  auto rows=doc["reads"].to<JsonArray>();
  for(size_t index=0;index<scan.count();++index){
    const auto* pair=scan.pair(index);auto row=rows.add<JsonArray>();
    whole_arm_read_json(row.add<JsonArray>(),pair->target);
    whole_arm_read_json(row.add<JsonArray>(),pair->feedback);
  }
  if(doc.overflowed()||measureJson(doc)>=capacity)return false;
  return serializeJson(doc,output,capacity)>0;
}
}

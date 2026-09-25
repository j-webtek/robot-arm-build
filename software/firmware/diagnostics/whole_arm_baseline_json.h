// Compact, versioned rows preserve every read without seven duplicated envelopes.
#pragma once
#include <ArduinoJson.h>
#include "whole_arm_baseline.h"
#include "servo_evidence_json.h"
namespace rocell_diag {
inline void whole_arm_read_json(JsonArray row,const ReadEvidence& read) {
  row.add(read.sequence);row.add(read.started_us);row.add(read.finished_us);
  row.add(read.returned_bytes);row.add(read.device_error);
  const bool success=read.status==ReadStatus::Succeeded;row.add(success);
  if(!success){row.add(nullptr);return;}
  char raw[31]={};static const char hex[]="0123456789abcdef";
  for(size_t i=0;i<read.width;++i){raw[2*i]=hex[read.bytes[i]>>4];raw[2*i+1]=hex[read.bytes[i]&15];}
  row.add(raw);
}
inline bool whole_arm_baseline_json(const WholeArmBaseline& gate,const char* boot,const char* command,
                                    char* out,size_t capacity) {
  if(!out||!capacity)return false;out[0]=0;
  if(!valid_identity(boot)||!valid_identity(command)||!gate.count())return false;
  JsonDocument doc;doc["schema"]="rocell.whole_arm_baseline.v1";
  doc["boot_id"]=boot;doc["command_id"]=command;
  doc["profile_id"]="waveshare-sms-sts-reference-b8b377642b3e";doc["byte_order"]="little";
  doc["accepted"]=gate.accepted();doc["reason"]=gate.reason();doc["checked_us"]=gate.checked_us();
  auto policy=doc["policy"].to<JsonObject>();const auto& p=gate.policy();
  policy["tracking_tolerance"]=p.tracking_tolerance;policy["maximum_pair_us"]=p.maximum_pair_us;
  policy["maximum_scan_us"]=p.maximum_scan_us;policy["maximum_age_us"]=p.maximum_age_us;
  auto joints=policy["joints"].to<JsonArray>();
  for(const auto& window:p.joints){auto pair=joints.add<JsonArray>();pair.add(window.minimum);pair.add(window.maximum);}
  auto rows=doc["reads"].to<JsonArray>();
  for(size_t i=0;i<gate.count();++i){
    const auto* pair=gate.pair(i);auto row=rows.add<JsonArray>();
    whole_arm_read_json(row.add<JsonArray>(),pair->target);
    whole_arm_read_json(row.add<JsonArray>(),pair->feedback);
  }
  if(doc.overflowed()||measureJson(doc)>=capacity)return false;
  return serializeJson(doc,out,capacity)>0;
}
}

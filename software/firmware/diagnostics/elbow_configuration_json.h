#pragma once
#include "elbow_configuration_snapshot.h"
#include "hold_evidence_json.h"
namespace rocell_diag {
inline bool elbow_configuration_json(const ElbowConfigurationSnapshot& scan,
    const char* boot,const char* capture,char* out,size_t capacity){
  if(!out||!capacity)return false;
  out[0]=0;
  if(!valid_identity(boot)||!valid_identity(capture))return false;
  JsonDocument doc;doc["schema"]="rocell.elbow_configuration.v1";
  doc["boot_id"]=boot;doc["capture_id"]=capture;
  doc["profile_id"]="waveshare-sms-sts-reference-b8b377642b3e";
  doc["byte_order"]="little";doc["complete"]=scan.complete();doc["reason"]=scan.reason();
  auto rows=doc["reads"].to<JsonArray>();
  for(size_t i=0;i<scan.count();++i)hold_read_row(rows,*scan.read(i));
  return hold_json_finish(doc,out,capacity);
}
}

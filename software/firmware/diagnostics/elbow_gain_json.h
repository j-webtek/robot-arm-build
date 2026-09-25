#pragma once
#include "elbow_gain_snapshot.h"
#include "hold_evidence_json.h"
namespace rocell_diag {
inline bool elbow_gain_json(const ElbowGainSnapshot& scan,
    const char* boot,const char* capture,char* out,size_t capacity){
  if(!out||!capacity)return false;
  out[0]=0;
  if(!valid_identity(boot)||!valid_identity(capture))return false;
  JsonDocument doc;doc["schema"]="rocell.elbow_gain.v1";
  doc["boot_id"]=boot;doc["capture_id"]=capture;
  doc["profile_id"]="roarm-m3-gain-reference-e8d5fc95a60f";
  doc["byte_order"]="little";doc["complete"]=scan.complete();doc["reason"]=scan.reason();
  auto rows=doc["reads"].to<JsonArray>();
  for(size_t i=0;i<scan.count();++i)hold_read_row(rows,*scan.read(i));
  return hold_json_finish(doc,out,capacity);
}
}

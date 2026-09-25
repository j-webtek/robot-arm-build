// Read-only serialization; no socket, admission, poll, reset or motion calls.
// Request owner must serialize access with runtime polling/return admission.
#pragma once
#include "held_pair_authenticated_runtime.h"
namespace rocell_diag {
inline const char* held_pair_phase_name(HeldPairPhase phase){
  switch(phase){
    case HeldPairPhase::New:return "NEW";
    case HeldPairPhase::Forward:return "FORWARD";
    case HeldPairPhase::AwaitingExport:return "AWAITING_EXPORT";
    case HeldPairPhase::Return:return "RETURN";
    case HeldPairPhase::Complete:return "COMPLETE";
    default:return "STOPPED";
  }
}
template<class Runtime> bool held_pair_status_json(const Runtime& runtime,char* out,size_t capacity){
  if(!runtime.session_hash())return false;
  JsonDocument doc;doc["schema"]="rocell.held_pair_transport.v1";
  doc["boot_id"]=runtime.boot_id();doc["session_sha256"]=runtime.session_hash();
  doc["leg"]=runtime.active_leg();doc["plan_sha256"]=runtime.active_plan_hash();
  doc["state"]=held_pair_phase_name(runtime.phase());doc["reason"]=runtime.reason();
  doc["records"]=runtime.evidence().size();doc["record_bytes"]=4096;
  doc["storage_fault"]=runtime.evidence().faulted();doc["durable_export_verified"]=false;
  return hold_json_finish(doc,out,capacity);
}
template<class Runtime> bool held_pair_record_json(const Runtime& runtime,size_t index,char* out,size_t capacity){
  if(!runtime.session_hash()||(runtime.phase()!=HeldPairPhase::AwaitingExport&&
       runtime.phase()!=HeldPairPhase::Complete&&runtime.phase()!=HeldPairPhase::Stopped))return false;
  const auto* row=runtime.evidence().get(index);if(!row)return false;
  JsonDocument doc;doc["schema"]="rocell.held_pair_record.v1";
  doc["boot_id"]=runtime.boot_id();doc["session_sha256"]=runtime.session_hash();
  doc["leg"]=runtime.active_leg();doc["plan_sha256"]=runtime.active_plan_hash();
  doc["index"]=index;doc["kind"]=row->kind;
  // A JSON string preserves exact internal JSON bytes through host decoding.
  // Do not embed a parsed object that the host would have to reserialize.
  doc["raw_json"]=row->json;
  return hold_json_finish(doc,out,capacity);
}
}

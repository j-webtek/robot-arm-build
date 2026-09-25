// Bounded record serialization, identity binding only (not authentication).
#pragma once
#include "hold_initialization_owner.h"
#include "whole_arm_baseline_json.h"
namespace rocell_diag {
inline bool hold_json_finish(JsonDocument& doc,char* out,size_t capacity){
  if(doc.overflowed()||measureJson(doc)>=capacity)return false;
  return serializeJson(doc,out,capacity)>0;
}
inline void hold_read_row(JsonArray rows,const ReadEvidence& read){
  auto row=rows.add<JsonArray>();row.add(read.servo_id);row.add(read.address);row.add(read.width);
  whole_arm_read_json(row.add<JsonArray>(),read);
}
inline bool hold_snapshot_json(const HoldStateSnapshot& scan,size_t index,
    const char* boot,const char* command,char* out,size_t capacity){
  if(!out||!capacity)return false;out[0]=0;
  if(index>=8||!valid_identity(boot)||!valid_identity(command))return false;
  JsonDocument doc;doc["schema"]="rocell.hold_snapshot.v1";
  doc["boot_id"]=boot;doc["command_id"]=command;doc["snapshot_index"]=index;
  doc["profile_id"]="waveshare-sms-sts-reference-b8b377642b3e";
  doc["byte_order"]="little";doc["complete"]=scan.complete();doc["reason"]=scan.reason();
  auto rows=doc["reads"].to<JsonArray>();
  for(size_t i=0;i<scan.positions().count();++i){
    const auto* pair=scan.positions().pair(i);
    hold_read_row(rows,pair->target);hold_read_row(rows,pair->feedback);
  }
  for(size_t i=0;const auto* read=scan.controls().read(i);++i)hold_read_row(rows,*read);
  return hold_json_finish(doc,out,capacity);
}
inline bool hold_action_json(const HoldActionEvidence& action,size_t index,
    const char* boot,const char* command,char* out,size_t capacity){
  if(!out||!capacity)return false;out[0]=0;
  if(index>=2||!valid_identity(boot)||!valid_identity(command)||action.servo_id!=14||
     !((action.address==41&&action.width==7)||(action.address==40&&action.width==1)))return false;
  JsonDocument doc;doc["schema"]="rocell.hold_action.v1";
  doc["boot_id"]=boot;doc["command_id"]=command;doc["action_index"]=index;
  doc["servo_id"]=action.servo_id;doc["address"]=action.address;doc["width"]=action.width;
  char raw[15]={};const char* hex="0123456789abcdef";
  for(size_t i=0;i<action.width;++i){raw[2*i]=hex[action.bytes[i]>>4];raw[2*i+1]=hex[action.bytes[i]&15];}
  doc["payload_hex"]=raw;doc["payload_source"]="PINNED_LIBRARY_ARGUMENT_ENCODING";
  doc["started_us"]=action.started_us;doc["finished_us"]=action.finished_us;
  doc["library_return"]=action.ack.library_return;doc["device_error"]=action.ack.device_error;
  doc["ack_policy"]=action.ack.ack_policy==AckPolicy::Enabled?"ENABLED":"UNVERIFIED";
  doc["dispatch_status"]=action.ack.status==DispatchStatus::Succeeded?"SUCCEEDED":
      (action.ack.status==DispatchStatus::Failed?"FAILED":"UNKNOWN");
  return hold_json_finish(doc,out,capacity);
}
inline bool hold_terminal_json(const HoldInitializationOwner& owner,const char* boot,
    const char* command,char* out,size_t capacity){
  if(!out||!capacity)return false;out[0]=0;
  if(!valid_identity(boot)||!valid_identity(command)||
     (owner.phase()!=HoldPhase::Captured&&owner.phase()!=HoldPhase::Fault))return false;
  JsonDocument doc;doc["schema"]="rocell.hold_terminal.v1";
  doc["boot_id"]=boot;doc["command_id"]=command;
  doc["state"]=owner.phase()==HoldPhase::Captured?"CAPTURED":"FAULT";
  doc["reason"]=owner.reason();doc["snapshot_count"]=owner.scan_count();
  doc["action_count"]=owner.action_count();doc["whole_arm_ready"]=false;
  return hold_json_finish(doc,out,capacity);
}
}

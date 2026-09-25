#pragma once
#include "pose_observation_sequence.h"
#include "hold_evidence_json.h"
namespace rocell_diag {
inline bool pose_observation_record(const PoseObservationSequence& sequence,size_t index,
    const char* boot,const char* id,char* out,size_t capacity){
  if(!out||!capacity)return false;out[0]=0;
  using State=PoseObservationSequence::State;
  if(!valid_identity(boot)||!valid_identity(id)||index>sequence.size()||
     (sequence.state()!=State::Captured&&sequence.state()!=State::Fault))return false;
  JsonDocument doc;doc["boot_id"]=boot;doc["command_id"]=id;
  if(index==sequence.size()){
    doc["schema"]="rocell.pose_observation_terminal.v1";
    doc["snapshot_count"]=sequence.size();doc["action_count"]=0;
    doc["state"]=sequence.state()==State::Captured?"CAPTURED":"FAULT";
    doc["reason"]=sequence.reason();
  }else{
    const auto& scan=*sequence.snapshot(index);
    doc["schema"]="rocell.pose_observation_snapshot.v1";
    doc["snapshot_index"]=index;doc["profile_id"]="waveshare-sms-sts-reference-b8b377642b3e";
    doc["byte_order"]="little";doc["complete"]=scan.complete();doc["reason"]=scan.reason();
    auto rows=doc["reads"].to<JsonArray>();
    for(size_t i=0;i<scan.positions().count();++i){
      const auto* pair=scan.positions().pair(i);
      hold_read_row(rows,pair->target);hold_read_row(rows,pair->feedback);
    }
    for(size_t i=0;const auto* read=scan.controls().read(i);++i)hold_read_row(rows,*read);
  }
  return hold_json_finish(doc,out,capacity);
}
}

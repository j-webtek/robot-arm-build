// Record encoding only. A sink must durably persist bytes; no bus/network API.
#pragma once
#include "shoulder_hold_candidate.h"
#include "hold_evidence_json.h"
#include <cstring>
namespace rocell_diag {
inline bool shoulder_event_json(const char* event,const ShoulderPreloadPose& pose,
    int sid,int result,const char* boot,const char* command,unsigned sequence,
    char* out,size_t capacity){
  if(!out||!capacity)return false;out[0]=0;
  if(!valid_identity(boot)||!valid_identity(command)||sequence>=64||!event)return false;
  const char* names[]={"BASELINE","BASELINE_STABILITY","PRELOAD_INTENT","PRELOAD_RESULT","PRELOAD_VERIFIED",
    "PAIR_ENABLE_INTENT","PAIR_ENABLE_SENT_UNACKNOWLEDGED","PAIR_ENABLE_READBACK","TIMED_HOLD_SAMPLE","STATE_MISMATCH",
    "SHOULDER_STEP_INTENT","SHOULDER_STEP_SENT","SHOULDER_STEP_SAMPLE","FAULT_SETTLING_SAMPLE"};
  bool known=false;for(auto name:names)if(strcmp(event,name)==0)known=true;
  if(!known||!pose.started_us||pose.finished_us<pose.started_us)return false;
  const bool preload=strncmp(event,"PRELOAD_",8)==0;
  const bool preparation=strcmp(command,"pose-preparation-v1")==0;
  if(preload?(preparation?(sid!=11&&sid!=15&&sid!=16&&sid!=17):(sid!=12&&sid!=13)):sid!=0)return false;
  JsonDocument doc;doc["schema"]="rocell.shoulder_hold_event.v1";
  doc["boot_id"]=boot;doc["command_id"]=command;doc["sequence"]=sequence;
  doc["event"]=event;doc["servo_id"]=sid;doc["result"]=result;
  doc["scan_started_us"]=pose.started_us;doc["scan_finished_us"]=pose.finished_us;
  // For action records the scan precedes transmission: do not call it readback.
  doc["snapshot_role"]=(strcmp(event,"PRELOAD_RESULT")==0||
      strcmp(event,"SHOULDER_STEP_SENT")==0||
      strcmp(event,"PAIR_ENABLE_SENT_UNACKNOWLEDGED")==0)?"PRE_ACTION":"OBSERVATION";
  if(strcmp(event,"PRELOAD_INTENT")==0||strcmp(event,"PRELOAD_RESULT")==0){
    doc["requested_target"]=pose.requested_target;doc["speed"]=20;doc["acceleration"]=1;
  }
  if(strcmp(event,"PRELOAD_RESULT")==0){
    doc["action_started_us"]=pose.action_started_us;doc["action_finished_us"]=pose.action_finished_us;
    doc["device_error"]=pose.action_device_error;
  }
  if(strncmp(event,"SHOULDER_STEP_",14)==0){
    auto targets=doc["requested_targets"].to<JsonArray>();
    targets.add(pose.requested_pair[0]);targets.add(pose.requested_pair[1]);
    doc["speed"]=20;doc["acceleration"]=1;
    if(strcmp(event,"SHOULDER_STEP_SENT")==0){
      doc["delivery"]="SENT_UNACKNOWLEDGED";
      doc["action_started_us"]=pose.action_started_us;doc["action_finished_us"]=pose.action_finished_us;
    }
  }
  auto rows=doc["joints"].to<JsonArray>();const char* hex="0123456789abcdef";
  for(unsigned i=0;i<7;++i){
    auto row=rows.add<JsonArray>();row.add(i+11);row.add(pose.position[i]);row.add(pose.goal[i]);row.add(pose.torque[i]);
    char raw[31]={};for(unsigned j=0;j<15;++j){raw[j*2]=hex[pose.feedback[i][j]>>4];raw[j*2+1]=hex[pose.feedback[i][j]&15];}
    row.add(raw);
  }
  doc["physical_accuracy_verified"]=false;return hold_json_finish(doc,out,capacity);
}
inline bool shoulder_hold_terminal_json(const ShoulderHoldCandidate& owner,const char* boot,
    const char* command,unsigned record_count,char* out,size_t capacity){
  if(!out||!capacity)return false;out[0]=0;
  if(!valid_identity(boot)||!valid_identity(command)||record_count>64)return false;
  JsonDocument doc;doc["schema"]="rocell.shoulder_hold_terminal.v1";
  doc["boot_id"]=boot;doc["command_id"]=command;doc["record_count"]=record_count;
  doc["reason"]=owner.reason();doc["timed_observation_complete"]=owner.observation_complete();
  doc["enable_delivery"]=owner.delivery()==ShoulderEnableDelivery::NotAttempted?
    "NOT_ATTEMPTED":"SENT_UNACKNOWLEDGED";
  doc["whole_arm_ready"]=false;doc["lift_authorized"]=false;
  return hold_json_finish(doc,out,capacity);
}
template<class Sink> class ShoulderHoldEvidenceSink {
 public:
  ShoulderHoldEvidenceSink(Sink& sink,const char* boot,const char* command):sink_(sink),boot_(boot),command_(command){}
  bool operator()(const char* event,const ShoulderPreloadPose& pose,int sid,int result){
    if(failed_)return false;
    if(!shoulder_event_json(event,pose,sid,result,boot_,command_,sequence_,buffer_,sizeof(buffer_))||
       !sink_.persist(sequence_,buffer_,strlen(buffer_))){failed_=true;return false;}
    ++sequence_;return true;
  }
  unsigned count()const{return sequence_;}
 private:
  Sink& sink_;const char* boot_;const char* command_;unsigned sequence_=0;bool failed_=false;
  char buffer_[4096]={};
};
}

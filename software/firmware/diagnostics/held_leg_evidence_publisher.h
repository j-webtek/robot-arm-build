// Raw single-leg evidence only; no authentication, live route or return admission.
// Capacity: 32 snapshots, one write and one terminal; each record <4096 bytes.
#pragma once
#include "held_elbow_leg_owner.h"
#include "hold_evidence_json.h"
namespace rocell_diag {
inline bool held_leg_snapshot_json(const HoldStateSnapshot& scan,size_t index,
    const char* boot,const char* command,char* out,size_t capacity,const char* captured_reason=nullptr){
  if(!out||!capacity)return false;out[0]=0;
  if(index>=32||!valid_identity(boot)||!valid_identity(command))return false;
  JsonDocument doc;doc["schema"]="rocell.held_leg_snapshot.v1";
  doc["boot_id"]=boot;doc["command_id"]=command;doc["snapshot_index"]=index;
  doc["profile_id"]="waveshare-sms-sts-reference-b8b377642b3e";
  doc["byte_order"]="little";doc["complete"]=scan.complete();
  doc["reason"]=captured_reason?captured_reason:scan.reason();
  auto rows=doc["reads"].to<JsonArray>();
  for(size_t i=0;i<scan.positions().count();++i){
    const auto* p=scan.positions().pair(i);hold_read_row(rows,p->target);hold_read_row(rows,p->feedback);
  }
  for(size_t i=0;const auto* r=scan.controls().read(i);++i)hold_read_row(rows,*r);
  return hold_json_finish(doc,out,capacity);
}
inline bool held_leg_terminal_json(const HeldElbowLegOwner& owner,const char* boot,
    const char* command,char* out,size_t capacity){
  if(!owner.terminal()||!valid_identity(boot)||!valid_identity(command))return false;
  JsonDocument doc;doc["schema"]="rocell.held_leg_terminal.v1";
  doc["boot_id"]=boot;doc["command_id"]=command;
  doc["state"]=owner.phase()==HeldLegPhase::Arrived?"ARRIVED":
      owner.phase()==HeldLegPhase::NotArrived?"NOT_ARRIVED":"FAULT";
  doc["reason"]=owner.reason();doc["snapshot_count"]=owner.scan_count();
  doc["action_count"]=owner.action()?1:0;doc["whole_arm_ready"]=false;
  return hold_json_finish(doc,out,capacity);
}
class HeldLegEvidencePublisher {
 public:
  template<class Sink> bool begin(Sink& sink,const char* boot,const char* command){
    if(attempted_)return false;attempted_=true;
    if(!valid_identity(boot)||!valid_identity(command)||!sink.reserve(34))return false;
    memcpy(boot_,boot,strlen(boot)+1);memcpy(command_,command,strlen(command)+1);
    ready_=true;return true;
  }
  template<class Bus,class Clock,class Sink>
  void poll(HeldElbowLegOwner& owner,Bus& bus,Clock& clock,Sink& sink){
    if(faulted_||terminal_)return;
    if(!ready_||sink.faulted()){stop(owner);return;}
    owner.poll(bus,clock);
    while(scans_<owner.scan_count()){
      if(!held_leg_snapshot_json(*owner.scan(scans_),scans_,boot_,command_,buffer_,sizeof(buffer_))||
         !sink.publish("held_leg_scan",buffer_)){stop(owner);return;}
      ++scans_;
    }
    if(!action_&&owner.action()){
      // Preserve the established raw action encoding; distinct envelope kind.
      if(!hold_action_json(*owner.action(),0,boot_,command_,buffer_,sizeof(buffer_))||
         !sink.publish("held_leg_action",buffer_)){stop(owner);return;}
      action_=true;
    }
    if(owner.terminal()){
      // EvidenceStore kinds allow 15 bytes plus NUL. Keep the full schema in
      // JSON; the storage routing label must fit the actual fixed-size store.
      if(!held_leg_terminal_json(owner,boot_,command_,buffer_,sizeof(buffer_))||!sink.publish("held_leg_end",buffer_)){
        stop(owner);return;
      }
      terminal_=true;
    }
  }
  bool faulted()const{return faulted_;}
 private:
  void stop(HeldElbowLegOwner& owner){faulted_=true;owner.export_failed();}
  bool attempted_=false,ready_=false,faulted_=false,terminal_=false,action_=false;
  size_t scans_=0;char boot_[129]={},command_[129]={},buffer_[4096]={};
};
}

// Caller supplies a reserved bounded sink and authenticated/exclusive admission.
// This publisher adds no authorization or hardware route. Capacity: 8 scan and
// 2 action records and 1 terminal, each <=4095 bytes plus NUL. Faults retain evidence.
#pragma once
#include "hold_evidence_json.h"
namespace rocell_diag {
class HoldEvidencePublisher {
 public:
  template<class Sink>
  bool begin(Sink& sink,const char* boot,const char* command){
    if(attempted_)return false;attempted_=true;
    if(!valid_identity(boot)||!valid_identity(command)||!sink.reserve(11))return false;
    memcpy(boot_,boot,strlen(boot)+1);memcpy(command_,command,strlen(command)+1);
    ready_=true;return true;
  }
  template<class Library,class Clock,class Sink>
  void poll(HoldInitializationOwner& owner,Library& bus,Clock& clock,Sink& sink){
    if(faulted_||terminal_)return;
    if(!ready_||sink.faulted()){stop(owner);return;}
    owner.poll(bus,clock);
    // Record timestamps, not publication order, establish action/read ordering.
    while(scans_<owner.scan_count()){
      if(!hold_snapshot_json(*owner.scan(scans_),scans_,boot_,command_,buffer_,sizeof(buffer_))||
         !sink.publish("hold_scan",buffer_)){stop(owner);return;}
      ++scans_;
    }
    while(actions_<owner.action_count()){
      if(!hold_action_json(*owner.action(actions_),actions_,boot_,command_,buffer_,sizeof(buffer_))||
         !sink.publish("hold_action",buffer_)){stop(owner);return;}
      ++actions_;
    }
    if(owner.phase()==HoldPhase::Captured||owner.phase()==HoldPhase::Fault){
      if(!hold_terminal_json(owner,boot_,command_,buffer_,sizeof(buffer_))||
         !sink.publish("hold_terminal",buffer_)){stop(owner);return;}
      terminal_=true;
    }
  }
  bool faulted()const{return faulted_;}
 private:
  void stop(HoldInitializationOwner& owner){faulted_=true;owner.export_failed();}
  bool attempted_=false,ready_=false,faulted_=false,terminal_=false;
  size_t scans_=0,actions_=0;
  char boot_[129]={},command_[129]={},buffer_[4096]={};
};
}

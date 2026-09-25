// Candidate composition. No automatic installation or registration on r29.
// Same control task and sticky bus reservation as the faulted parent are required.
#pragma once
#include "shoulder_preload_session.h"
#include "shoulder_fault_settling_capture.h"
#include "shoulder_export_receipt.h"
namespace rocell_diag {
template<class Crypto,class Parent> class ShoulderFaultSettlingSession {
 public:
  using Verifier=ShoulderReceiptVerifier<Crypto>;
  ShoulderFaultSettlingSession(Crypto& crypto,Parent& parent,
      const uint8_t (&key)[32],const uint8_t (&boot)[16])
      :crypto_(crypto),parent_(parent),original_(crypto,key,boot,parent.command_id()),
       verifier_(crypto,key,boot,make_command(parent.command_id())),barrier_(crypto,verifier_){
    char expected[33]={};const char* hex="0123456789abcdef";
    for(int i=0;i<16;++i){expected[2*i]=hex[boot[i]>>4];expected[2*i+1]=hex[boot[i]&15];}
    valid_=valid_identity(command_)&&strcmp(expected,parent.boot_id())==0;
  }
  // This receipt signs the exact original fault bytes under the PARENT command.
  // It cannot clear its fault or consume its retained record.
  bool begin(const ShoulderReceiptView& receipt,uint64_t now){
    if(used_)return false;used_=true;
    if(!valid_||parent_.phase()!=ShoulderPreloadPhase::Fault||!parent_.record()||
       !crypto_.sha256(reinterpret_cast<const uint8_t*>(parent_.record()),parent_.record_size(),fault_hash_)||
       !original_.verify(receipt,parent_.sequence(),fault_hash_)){failed_=true;return false;}
    return capture_.begin(now,true,true);
  }
  template<class Bus,class Clock,class Admission>
  void advance(Bus& bus,Clock& clock,Admission& admitted){
    if(!used_||failed_)return;
    if(parent_.phase()!=ShoulderPreloadPhase::Fault){failed_=true;return;}
    capture_.advance(bus,clock,admitted);
    if(capture_.count()==published_)return;
    // Retain valid surprising scans even if the collector itself just failed.
    if(barrier_.state()!=ShoulderExportState::Empty){failed_=true;return;}
    const auto sequence=capture_.count()-1;
    if(!shoulder_event_json("FAULT_SETTLING_SAMPLE",capture_.record(),0,0,
        parent_.boot_id(),command_,sequence,scratch_,sizeof(scratch_))){failed_=true;return;}
    JsonDocument doc;
    if(deserializeJson(doc,scratch_)){failed_=true;return;}
    char hash[65]={};const char* hex="0123456789abcdef";
    for(int i=0;i<32;++i){hash[i*2]=hex[fault_hash_[i]>>4];hash[i*2+1]=hex[fault_hash_[i]&15];}
    doc["parent_command_id"]=parent_.command_id();doc["original_fault_sha256"]=hash;
    doc["parent_fault_latched"]=true;doc["movement_authorized"]=false;
    const auto now=clock.now_us();
    if(!hold_json_finish(doc,scratch_,sizeof(scratch_))||
       !barrier_.stage(sequence,scratch_,strlen(scratch_),now,now+8000000)){failed_=true;return;}
    published_=capture_.count();
  }
  bool receipt(const ShoulderReceiptView& value,uint64_t now){
    if(failed_||capture_.state()!=SettlingState::WaitingExport||
       !barrier_.accept(value,now)||!barrier_.consume()){
      failed_=true;return false;
    }
    return capture_.exported(published_-1,true,now);
  }
  const char* record()const{return barrier_.retained();}
  const char* command_id()const{return command_;}
  const char* boot_id()const{return parent_.boot_id();}
  unsigned count()const{return capture_.count();}
  SettlingState state()const{return failed_?SettlingState::Failed:capture_.state();}
  const char* reason()const{return failed_?"SETTLING_AUTH_OR_BINDING_FAILED":capture_.reason();}
 private:
  const char* make_command(const char* parent){
    if(parent&&strlen(parent)<=120)snprintf(command_,sizeof(command_),"settle-%s",parent);
    return command_;
  }
  Crypto& crypto_;Parent& parent_;char command_[129]={};
  Verifier original_,verifier_;ShoulderExportBarrier<Crypto,Verifier> barrier_;
  ShoulderFaultSettlingCapture capture_;bool used_=false,valid_=false,failed_=false;
  unsigned published_=0;uint8_t fault_hash_[32]={};char scratch_[4096]={};
};
}

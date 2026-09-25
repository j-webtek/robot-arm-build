// Single-loop acquisition owner. Reserve callback must atomically exclude ALL
// other bus users until reboot. It must not clear an existing fault or move.
#pragma once
#include "pose_observation_json.h"
namespace rocell_diag {
template<class ReadOnlyBus,class Clock>
class PoseObservationOwner {
 public:
  using Reserve=bool(*)(void*);
  PoseObservationOwner(ReadOnlyBus& bus,Clock& clock,Reserve reserve,void* context,
      const char* boot):bus_(bus),clock_(clock),reserve_(reserve),context_(context){
    if(valid_identity(boot))memcpy(boot_,boot,strlen(boot)+1);
  }
  bool request(const char* boot,const char* id){
    if(attempted_||!boot_[0]||!valid_identity(boot)||!valid_identity(id)||strcmp(boot,boot_))return false;
    attempted_=true;
    if(!reserve_||!reserve_(context_)){reason_="BUS_RESERVATION_DENIED";return false;}
    memcpy(id_,id,strlen(id)+1);
    if(!sequence_.begin(clock_.now_us())){reason_="OBSERVATION_START_FAILED";return false;}
    owned_=true;reason_="SAMPLING";return true;
  }
  void poll(){
    if(!owned_||finished_)return;
    sequence_.poll(bus_,clock_);
    using State=PoseObservationSequence::State;
    if(sequence_.state()!=State::Captured&&sequence_.state()!=State::Fault)return;
    finished_=true;
    for(size_t i=0;i<=sequence_.size();++i){
      if(!pose_observation_record(sequence_,i,boot_,id_,records_[i],sizeof(records_[i]))){
        export_fault_=true;reason_="OBSERVATION_SERIALIZATION_FAILED";return;
      }
      ++count_;
    }
    reason_=sequence_.reason();
  }
  bool active()const{return owned_&&!finished_;}
  bool attempted()const{return attempted_;}
  bool export_fault()const{return export_fault_;}
  const char* reason()const{return reason_;}
  size_t size()const{return finished_?count_:0;}
  const char* record(size_t index)const{return finished_&&index<count_?records_[index]:nullptr;}
 private:
  ReadOnlyBus& bus_;Clock& clock_;Reserve reserve_;void* context_;
  PoseObservationSequence sequence_;
  char boot_[129]={},id_[129]={},records_[4][4096]={};
  size_t count_=0;bool attempted_=false,owned_=false,finished_=false,export_fault_=false;
  const char* reason_="NOT_STARTED";
};
}

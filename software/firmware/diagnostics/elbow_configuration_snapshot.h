// Fixed read-only diagnostic; integration must provide exclusive inactive bus
// ownership. Not routed or installed. Raw values do not establish model/scaling.
#pragma once
#include <stddef.h>
#include <string.h>
#include "servo_evidence.h"
namespace rocell_diag {
class ElbowConfigurationSnapshot {
 public:
  static constexpr size_t register_count=12;
  template<class Library,class Clock>
  bool acquire(Library& bus,Clock& clock,bool (*inactive)(void*),void* context=nullptr){
    if(used_)return false;
    used_=true;
    if(bus.End!=0||!inactive){reason_="CONFIG_PRECONDITION_INVALID";return false;}
    // SMS_STS.h reference: model, limits, deadbands, offset, mode, torque,
    // acceleration, goal speed and torque limit. No caller-selected address.
    const uint8_t addresses[register_count]={3,9,11,26,27,31,33,40,41,46,48,55};
    const uint8_t widths[register_count]={2,2,2,1,1,2,1,1,1,2,2,1};
    uint64_t previous=0;
    for(size_t i=0;i<register_count;++i){
      if(!inactive(context)){reason_="CONFIG_BUS_NOT_INACTIVE";return false;}
      auto& r=reads_[i];r.servo_id=14;r.address=addresses[i];r.width=widths[i];
      r.sequence=static_cast<uint32_t>(i);r.started_us=clock.now_us();
      if(!r.started_us||r.started_us>INT64_MAX||(i&&r.started_us<previous)){
        reason_="CONFIG_CLOCK_INVALID";return false;
      }
      if(i&&r.started_us-reads_[0].started_us>500000){reason_="CONFIG_DEADLINE";return false;}
      count_=i+1;
      r.returned_bytes=bus.Read(14,r.address,r.bytes,r.width);
      r.finished_us=clock.now_us();
      r.device_error=r.returned_bytes==r.width?bus.Error:-1;
      const bool valid=r.returned_bytes==r.width&&r.device_error==0&&
        r.finished_us>=r.started_us&&r.finished_us<=INT64_MAX&&
        r.finished_us-r.started_us<=50000&&r.finished_us-reads_[0].started_us<=500000;
      r.status=valid?ReadStatus::Succeeded:ReadStatus::Failed;
      if(!valid){memset(r.bytes,0,sizeof(r.bytes));reason_="CONFIG_READ_INVALID";return false;}
      previous=r.finished_us;
    }
    if(!inactive(context)){reason_="CONFIG_BUS_NOT_INACTIVE";return false;}
    complete_=true;reason_="CONFIG_CAPTURED";return true;
  }
  bool complete()const{return complete_;}
  size_t count()const{return count_;}
  const ReadEvidence* read(size_t index)const{return index<count_?&reads_[index]:nullptr;}
  const char* reason()const{return reason_;}
 private:
  ReadEvidence reads_[register_count]={};size_t count_=0;
  bool used_=false,complete_=false;const char* reason_="NOT_STARTED";
};
}

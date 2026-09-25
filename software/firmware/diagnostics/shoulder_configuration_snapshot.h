// Candidate fixed read-only shoulder inventory; no installed routes or writes.
#pragma once
#include <stddef.h>
#include <string.h>
#include "servo_evidence.h"
namespace rocell_diag {
class ShoulderConfigurationSnapshot {
 public:
  static constexpr size_t registers_per_servo=17,maximum_reads=34;
  template<class Library,class Clock>
  bool acquire(Library& bus,Clock& clock,bool (*inactive)(void*),void* context=nullptr){
    if(used_)return false;
    used_=true;
    if(bus.End!=0||!inactive){reason_="SHOULDER_CONFIG_PRECONDITION";return false;}
    // Model, limits, P/D/I, deadbands, offset, mode, torque, acceleration,
    // goal, speed, torque limit, lock, and position-through-current block.
    const uint8_t addresses[]={3,9,11,21,22,23,26,27,31,33,40,41,42,46,48,55,56};
    const uint8_t widths[]={2,2,2,1,1,1,1,1,2,1,1,1,2,2,2,1,15};
    uint64_t previous=0;
    for(size_t i=0;i<maximum_reads;++i){
      if(!inactive(context)){reason_="SHOULDER_CONFIG_BUS_BUSY";return false;}
      auto& r=reads_[i];const size_t field=i%registers_per_servo;
      r.servo_id=12+i/registers_per_servo;r.address=addresses[field];r.width=widths[field];
      r.sequence=static_cast<uint32_t>(i);r.started_us=clock.now_us();
      if(!r.started_us||r.started_us>INT64_MAX||(i&&r.started_us<previous)){
        reason_="SHOULDER_CONFIG_CLOCK";return false;
      }
      if(i&&r.started_us-reads_[0].started_us>1000000){reason_="SHOULDER_CONFIG_DEADLINE";return false;}
      count_=i+1;r.returned_bytes=bus.Read(r.servo_id,r.address,r.bytes,r.width);
      r.finished_us=clock.now_us();r.device_error=r.returned_bytes==r.width?bus.Error:-1;
      const bool valid=r.returned_bytes==r.width&&r.device_error==0&&
          r.finished_us>=r.started_us&&r.finished_us<=INT64_MAX&&
          r.finished_us-r.started_us<=50000&&r.finished_us-reads_[0].started_us<=1000000;
      r.status=valid?ReadStatus::Succeeded:ReadStatus::Failed;
      if(!valid){memset(r.bytes,0,sizeof(r.bytes));reason_="SHOULDER_CONFIG_READ_INVALID";return false;}
      previous=r.finished_us;
    }
    if(!inactive(context)){reason_="SHOULDER_CONFIG_BUS_BUSY";return false;}
    complete_=true;reason_="SHOULDER_CONFIG_CAPTURED";return true;
  }
  bool complete()const{return complete_;}
  size_t count()const{return count_;}
  const ReadEvidence* read(size_t index)const{return index<count_?&reads_[index]:nullptr;}
  const char* reason()const{return reason_;}
 private:
  ReadEvidence reads_[maximum_reads]={};size_t count_=0;
  bool used_=false,complete_=false;const char* reason_="NOT_STARTED";
};
}

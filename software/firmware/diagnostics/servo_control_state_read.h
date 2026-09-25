// Direct one-byte reads from the pinned register map; no cached ReadMode(-1).
// ReadMode(-1) indexes 33-56 in its 56..70 feedback cache and is unsuitable here.
#pragma once
#include <stddef.h>
#include "servo_evidence.h"
namespace rocell_diag {
class ServoControlStateRead {
 public:
  template<class Library,class Clock>
  bool acquire(Library& library,Clock& clock){
    if(used_)return false;used_=true;
    if(library.End!=0){reason_="CONTROL_BYTE_ORDER_INVALID";return false;}
    uint64_t previous=0;
    for(size_t index=0;index<14;++index){
      auto& r=reads_[index];count_=index+1;
      r.servo_id=static_cast<uint8_t>(11+index/2);r.address=index%2?40:33;
      r.width=1;r.sequence=index;r.started_us=clock.now_us();
      r.returned_bytes=library.Read(r.servo_id,r.address,r.bytes,1);
      r.finished_us=clock.now_us();r.device_error=r.returned_bytes==1?library.Error:-1;
      const bool valid=r.returned_bytes==1 && r.device_error==0 &&
        // Calls are synchronous and ordered by sequence. Integer microsecond
        // timestamps may share an adjacent boundary; reject reversal, not equality.
        (index==0?r.started_us>0:r.started_us>=previous) &&
        r.finished_us>=r.started_us && r.finished_us<=INT64_MAX &&
        r.finished_us-r.started_us<=1000000 && r.finished_us-reads_[0].started_us<=7000000;
      r.status=valid?ReadStatus::Succeeded:ReadStatus::Failed;
      if(!valid){r.bytes[0]=0;reason_="CONTROL_READ_INVALID";return false;}
      previous=r.finished_us;
    }
    complete_=true;reason_="CONTROL_READ_CAPTURED";return true;
  }
  bool matches(uint8_t reviewed_mode,uint64_t now,uint64_t maximum_age_us){
    if(!complete_||faulted_)return false;
    if(!maximum_age_us||maximum_age_us>1000000||now>INT64_MAX||now<last_check_||
       now<reads_[13].finished_us||now-reads_[0].started_us>maximum_age_us){
      faulted_=true;reason_="CONTROL_READ_STALE";return false;
    }
    last_check_=now;
    for(size_t index=0;index<14;++index){
      if(reads_[index].bytes[0]!=(index%2?1:reviewed_mode)){
        faulted_=true;reason_="CONTROL_STATE_MISMATCH";return false;
      }
    }
    return true;
  }
  const ReadEvidence* read(size_t i)const{return i<count_?&reads_[i]:nullptr;}
  const char* reason()const{return reason_;}
 private:
  ReadEvidence reads_[14]={};size_t count_=0;uint64_t last_check_=0;
  bool used_=false,complete_=false,faulted_=false;
  const char* reason_="NOT_STARTED";
};
}

// Offline result-export barrier. The owner supplies immutable serialized results;
// request bodies must never substitute for controller-owned result bytes.
#pragma once
#include "shoulder_export_receipt.h"
namespace rocell_diag {
template<class Crypto> class CharacterizationExportBarrier {
 public:
  CharacterizationExportBarrier(Crypto& crypto,const uint8_t (&key)[32],
      const uint8_t (&boot)[16],const char* campaign)
      :crypto_(crypto),verifier_(crypto,key,boot,campaign) {}
  // Only one outstanding result. Invalid/reordered attempts latch the barrier.
  bool stage(unsigned leg,const uint8_t* result,size_t size,uint64_t now){
    if(failed_||pending_||leg!=completed_||leg>=12||!result||!size||size>16384||
        !now||now<last_time_){failed_=true;return false;}
    if(!crypto_.sha256(result,size,digest_)){failed_=true;return false;}
    pending_=true;issued_=last_time_=now;return true;
  }
  bool accept(const ShoulderReceiptView& receipt,uint64_t now){
    if(failed_||!pending_||now<last_time_||now-issued_>5000000||
        !verifier_.verify(receipt,completed_,digest_)){
      failed_=true;return false;
    }
    last_time_=now;pending_=false;++completed_;return true;
  }
  bool permits_next(unsigned leg)const{
    return !failed_&&!pending_&&completed_>0&&leg==completed_&&leg<12;
  }
  bool failed()const{return failed_;}
  unsigned completed()const{return completed_;}
 private:
  Crypto& crypto_;ShoulderReceiptVerifier<Crypto> verifier_;
  uint8_t digest_[32]={};unsigned completed_=0;
  bool pending_=false,failed_=false;uint64_t issued_=0,last_time_=0;
};
}

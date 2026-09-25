// Offline single-owner session. No network routes or board adapter.
// Allocate off the control-task stack; the owner retains bounded sample buffers.
#pragma once
#include "characterization_admission.h"
#include "characterization_fault_record.h"
namespace rocell_diag {
template<class Crypto> class CharacterizationSession {
 public:
  CharacterizationSession(Crypto& crypto,const uint8_t (&key)[32],const uint8_t (&boot)[16],
      const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires,
      const uint8_t (&campaign)[32],const uint8_t (&reference)[32],
      const CharacterizationManifest& expected)
      :crypto_(crypto),identity_(campaign),admission_(key,boot,nonce,issued,expires,campaign,reference,expected),
       barrier_(crypto,key,boot,identity_.text) {}
  CharacterizationSession(const CharacterizationSession&)=delete;
  CharacterizationSession& operator=(const CharacterizationSession&)=delete;
  bool start(const uint8_t* token,size_t size,uint64_t now){
    if(attempted_)return false;
    attempted_=true;active_=admission_.start(token,size,now,crypto_,owner_);return active_;
  }
  template<class Bus,class Clock,class Evidence,class Admission>
  void advance(Bus& bus,Clock& clock,Evidence& evidence,Admission& admitted){
    if(!active_)return;
    owner_.advance(bus,clock,evidence,admitted);
    if(owner_.phase()==CharacterizationPhase::AwaitExport&&!pending_){
      pending_=owner_.stage_export(barrier_,clock.now_us());
    }
  }
  bool accept_export(const ShoulderReceiptView& receipt,uint64_t now){
    if(!active_)return false;
    // Hash before acceptance: never advance and then discover that recovery
    // evidence cannot be retained. This is the decoded 124-byte receipt digest.
    uint8_t digest[32];
    if(!receipt.bytes||receipt.size!=124||!crypto_.sha256(receipt.bytes,receipt.size,digest))return false;
    bool ok=owner_.accept_export(barrier_,receipt,now);
    if(ok){pending_=false;memcpy(last_receipt_,digest,32);has_receipt_=true;}
    return ok;
  }
  const char* campaign_id()const{return identity_.text;}
  CharacterizationPhase phase()const{return owner_.phase();}
  unsigned completed()const{return owner_.completed();}
  unsigned writes()const{return owner_.writes();}
  bool last_receipt(uint8_t (&digest)[32])const{
    memcpy(digest,last_receipt_,32);return has_receipt_;
  }
  // Includes a staged result retained after an export timeout. Never relabel
  // leftover bytes from an accepted predecessor as the current leg's result.
  bool recovery_record(unsigned& leg,size_t& size,uint8_t (&digest)[32]){
    leg=0;size=0;memset(digest,0,32);
    if(!pending_||!owner_.result_size())return false;
    if(!crypto_.sha256(owner_.result_bytes(),owner_.result_size(),digest))return false;
    leg=owner_.completed();size=owner_.result_size();return true;
  }
  const uint8_t* result_bytes()const{return owner_.result_bytes();}
  size_t result_size()const{return owner_.result_size();}
  const CharacterizationFault& fault()const{return owner_.fault();}
  // Owner-thread-only read interface. No acquisition, dispatch or lifecycle change.
  // Network handlers must authenticate the session before calling these methods.
  bool record_info(unsigned& leg,size_t& size,uint8_t (&digest)[32]){
    leg=0;size=0;memset(digest,0,32);
    const bool failed=owner_.phase()==CharacterizationPhase::Fault&&owner_.result_size()>0;
    if(!failed&&(owner_.phase()!=CharacterizationPhase::AwaitExport||!pending_))return false;
    if(!crypto_.sha256(owner_.result_bytes(),owner_.result_size(),digest))return false;
    leg=owner_.completed();size=owner_.result_size();return true;
  }
  bool record_chunk(unsigned leg,const uint8_t (&expected_digest)[32],size_t offset,
                    uint8_t* output,size_t capacity,size_t& written){
    written=0;unsigned current;size_t size;uint8_t digest[32];
    if(!output||!capacity||capacity>1024||!record_info(current,size,digest)||
        leg!=current||memcmp(digest,expected_digest,32)||offset>=size)return false;
    written=size-offset<capacity?size-offset:capacity;
    memcpy(output,owner_.result_bytes()+offset,written);return true;
  }
 private:
  struct Identity {
    char text[65]={};
    explicit Identity(const uint8_t (&bytes)[32]){
      const char* hex="0123456789abcdef";
      for(unsigned i=0;i<32;++i){text[2*i]=hex[bytes[i]>>4];text[2*i+1]=hex[bytes[i]&15];}
    }
  };
  Crypto& crypto_;Identity identity_;CharacterizationAdmission admission_;
  CharacterizationExportBarrier<Crypto> barrier_;ShoulderCharacterizationOwner owner_;
  bool attempted_=false,active_=false,pending_=false;
  uint8_t last_receipt_[32]={};bool has_receipt_=false;
};
}

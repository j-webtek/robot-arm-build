// Immutable logical records backed by the retained raw leg history. Regenerate
// JSON on demand and verify its publication-time hash before exposing bytes.
// One scratch Record: get() pointers expire on the next get/publish call.
// Owner must outlive this store and must not be reconstructed before rollover.
#pragma once
#include "held_leg_evidence_publisher.h"
namespace rocell_diag {
template<class Crypto> class HeldCompactEvidenceStore {
 public:
  struct Record {char kind[16];char json[4096];};
  HeldCompactEvidenceStore()=default;
  HeldCompactEvidenceStore(const HeldCompactEvidenceStore&)=delete;
  HeldCompactEvidenceStore& operator=(const HeldCompactEvidenceStore&)=delete;
  bool bind(const HeldElbowLegOwner& owner,Crypto& crypto,const char* boot,const char* command){
    if(owner_||fault_||!valid_identity(boot)||!valid_identity(command))return fail();
    owner_=&owner;crypto_=&crypto;memcpy(boot_,boot,strlen(boot)+1);memcpy(command_,command,strlen(command)+1);
    return true;
  }
  bool reserve(size_t n){
    if(fault_||!owner_||reserved_||n!=34)return fail();reserved_=true;return true;
  }
  bool publish(const char* kind,const char* json){
    if(fault_||!reserved_||terminal_||count_==34||!kind||!json)return fail();
    size_t length=0;while(length<4096&&json[length])++length;
    if(!length||length>=4096)return fail();
    auto& entry=entries_[count_];
    if(!strcmp(kind,"held_leg_scan")){
      if(scans_>=owner_->scan_count()||scans_>=32)return fail();
      entry.type=0;entry.scan=uint8_t(scans_);
      const char* reason=owner_->scan(scans_)->reason();size_t n=strlen(reason);
      if(n>=sizeof(entry.reason))return fail();memcpy(entry.reason,reason,n+1);
    }else if(!strcmp(kind,"held_leg_action")){
      if(action_||!owner_->action())return fail();entry.type=1;
    }else if(!strcmp(kind,"held_leg_end")){
      if(!owner_->terminal()||length>=sizeof(terminal_json_))return fail();entry.type=2;
      // Terminal reason may change on a subsequent external fault. Retain its
      // exact publication bytes instead of reconstructing from later state.
      if(!held_leg_terminal_json(*owner_,boot_,command_,scratch_.json,sizeof(scratch_.json))||
         strcmp(scratch_.json,json))return fail();
      memcpy(terminal_json_,json,length+1);
    }else return fail();
    if(!render(entry)||strcmp(scratch_.kind,kind)||strcmp(scratch_.json,json)||
       !crypto_->sha256(reinterpret_cast<const uint8_t*>(json),length,entry.digest))return fail();
    ++count_;if(entry.type==0)++scans_;if(entry.type==1)action_=true;if(entry.type==2)terminal_=true;
    return true;
  }
  const Record* get(size_t index)const{
    if(fault_||index>=count_)return nullptr;
    const auto& entry=entries_[index];uint8_t digest[32];
    if(!render(entry)||!crypto_->sha256(reinterpret_cast<const uint8_t*>(scratch_.json),
          strlen(scratch_.json),digest)||memcmp(digest,entry.digest,32)){fail();return nullptr;}
    return &scratch_;
  }
  size_t size()const{return count_;}
  bool faulted()const{return fault_;}
 private:
  struct Entry {uint8_t type=0,scan=0;char reason[64]={};uint8_t digest[32]={};};
  bool render(const Entry& entry)const{
    const char* kind=entry.type==0?"held_leg_scan":entry.type==1?"held_leg_action":"held_leg_end";
    memcpy(scratch_.kind,kind,strlen(kind)+1);
    if(entry.type==0){
      const auto* scan=owner_->scan(entry.scan);
      return scan&&held_leg_snapshot_json(*scan,entry.scan,boot_,command_,scratch_.json,
                                         sizeof(scratch_.json),entry.reason);
    }
    if(entry.type==1){const auto* action=owner_->action();
      return action&&hold_action_json(*action,0,boot_,command_,scratch_.json,sizeof(scratch_.json));}
    memcpy(scratch_.json,terminal_json_,strlen(terminal_json_)+1);return true;
  }
  bool fail()const{fault_=true;return false;}
  const HeldElbowLegOwner* owner_=nullptr;Crypto* crypto_=nullptr;
  Entry entries_[34];size_t count_=0,scans_=0;
  bool reserved_=false,action_=false,terminal_=false;mutable bool fault_=false;
  char boot_[129]={},command_[129]={},terminal_json_[1024]={};mutable Record scratch_{};
};
}

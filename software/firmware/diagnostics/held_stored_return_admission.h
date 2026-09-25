// Offline integration adapter: match retained records to the completed owner,
// derive their digest locally, then consume the signed continuation once.
// Session/plan IDs must come from initial authenticated admission, not a request.
// Host export digest remains a signed assertion; host durability is checked there.
#pragma once
#include "held_leg_evidence_publisher.h"
#include "held_evidence_digest.h"
#include "held_return_admission.h"
namespace rocell_diag {
class HeldStoredReturnAdmission {
 public:
  template<class Store,class Crypto>
  bool consume(HeldReturnAdmission& gate,const uint8_t* token,size_t length,
      uint64_t now,Crypto& crypto,const Store& store,const HeldElbowLegOwner& forward,
      const char* boot,const char* command,const char* session_hash,
      const char* plan_hash,uint16_t anchor){
    if(attempted_)return false;attempted_=true;
    if(store.faulted()||forward.phase()!=HeldLegPhase::Arrived||
       !forward.action()||forward.anchor()!=anchor||forward.scan_count()<5||
       store.size()!=forward.scan_count()+2)return false;
    size_t row=0;
    for(size_t i=0;i<forward.scan_count();++i){
      if(!held_leg_snapshot_json(*forward.scan(i),i,boot,command,buffer_,sizeof(buffer_))||
         !matches(store,row++,"held_leg_scan"))return false;
      if(i==2){
        if(!hold_action_json(*forward.action(),0,boot,command,buffer_,sizeof(buffer_))||
           !matches(store,row++,"held_leg_action"))return false;
      }
    }
    if(!held_leg_terminal_json(forward,boot,command,buffer_,sizeof(buffer_))||
       !matches(store,row,"held_leg_end")||!digest_.compute(store,crypto))return false;
    return gate.consume(token,length,now,crypto,session_hash,plan_hash,digest_.value(),anchor,true);
  }
 private:
  template<class Store> bool matches(const Store& store,size_t i,const char* kind){
    const auto* row=store.get(i);
    return row&&!strcmp(row->kind,kind)&&!strcmp(row->json,buffer_);
  }
  bool attempted_=false;HeldEvidenceDigest digest_;char buffer_[4096]={};
};
}

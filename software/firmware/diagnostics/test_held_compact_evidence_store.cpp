#define HELD_STORED_NO_MAIN
#include "test_held_stored_return_admission.cpp"
#include "held_compact_evidence_store.h"
struct FaultCrypto:Crypto{
  bool failed=false;
  bool sha256(const uint8_t* bytes,size_t size,uint8_t (&out)[32]){
    return !failed&&Crypto::sha256(bytes,size,out);
  }
};
struct Mirror{
  EvidenceStore<34,4096>& full;HeldCompactEvidenceStore<FaultCrypto>& compact;
  bool reserve(size_t n){return full.reserve(n)&&compact.reserve(n);}
  bool faulted()const{return full.faulted()||compact.faulted();}
  bool publish(const char* kind,const char* json){return full.publish(kind,json)&&compact.publish(kind,json);}
};
int main(){
  for(int scenario=0;scenario<3;++scenario){
    Bus bus;Clock clock;FaultCrypto crypto;bus.stuck=scenario==1;bus.bad=scenario==2?15:-1;
    auto owner=std::unique_ptr<HeldElbowLegOwner>(new HeldElbowLegOwner(policy(),2908,2,healthy));
    auto full=std::unique_ptr<EvidenceStore<34,4096>>(new EvidenceStore<34,4096>());
    auto compact=std::unique_ptr<HeldCompactEvidenceStore<FaultCrypto>>(new HeldCompactEvidenceStore<FaultCrypto>());
    assert(compact->bind(*owner,crypto,"boot","forward"));
    Mirror sink{*full,*compact};HeldLegEvidencePublisher publisher;
    assert(publisher.begin(sink,"boot","forward"));
    for(int i=0;i<30;++i){clock.tick+=110000;publisher.poll(*owner,bus,clock,sink);}
    assert(owner->terminal()&&!sink.faulted()&&full->size()==compact->size());
    for(size_t i=0;i<full->size();++i){
      const auto* row=compact->get(i);assert(row);
      assert(!strcmp(row->kind,full->get(i)->kind)&&!strcmp(row->json,full->get(i)->json));
    }
    // Freeze terminal bytes and capture-time reason despite later fault state.
    owner->interference();
    if(scenario!=2){auto* scan=const_cast<HoldStateSnapshot*>(owner->scan(0));
      assert(!scan->fresh(clock.tick+1000000,250000));}
    for(size_t i=0;i<full->size();++i){const auto* row=compact->get(i);assert(row);
      assert(!strcmp(row->json,full->get(i)->json));}
    crypto.failed=true;assert(!compact->get(0)&&compact->faulted());
    crypto.failed=false;assert(!compact->get(0)); // No implicit recovery.
  }
  {Bus bus;Clock clock;FaultCrypto crypto;HeldElbowLegOwner owner(policy(),2908,2,healthy);
   auto store=std::unique_ptr<HeldCompactEvidenceStore<FaultCrypto>>(new HeldCompactEvidenceStore<FaultCrypto>());
   assert(!store->reserve(34)&&store->faulted());assert(bus.reads==0&&bus.writes==0);}
  return 0;
}

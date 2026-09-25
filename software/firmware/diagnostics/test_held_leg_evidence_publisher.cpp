#define main run_leg_cases
#include "test_held_elbow_leg_owner.cpp"
#undef main
#include <iostream>
#include <string>
#include <vector>
#include "held_leg_evidence_publisher.h"
#include "evidence_store.h"
struct Sink{
  bool reserved=false,failed=false;int fail_at=-1;std::vector<std::string> records;
  bool reserve(size_t n){assert(n==34);reserved=true;return true;}
  bool faulted()const{return failed;}
  bool publish(const char*,const char* text){
    assert(reserved&&records.size()<34&&strlen(text)<4096);
    if(int(records.size())==fail_at){failed=true;return false;}
    records.emplace_back(text);return true;
  }
};
int main(){
  // Base-owner cases run in their own harness. Nesting their large unoptimized
  // stack frame inside this publisher harness can exhaust the Windows stack.
  // Exercise the real fixed-size storage, not only the permissive vector fake.
  // Keep this large object static, as it must not live on an embedded task stack.
  {static EvidenceStore<34,4096> store;
   Bus b;Clock c;static HeldElbowLegOwner owner(policy(),2908,2,healthy);
   static HeldLegEvidencePublisher publisher;
   assert(publisher.begin(store,"test-boot","test-leg"));
   for(int i=0;i<30;++i){c.tick+=110000;publisher.poll(owner,b,c,store);}
   assert(!store.faulted()&&!publisher.faulted());
   assert(owner.phase()==HeldLegPhase::Arrived&&store.size()==7);
   assert(strstr(store.get(6)->json,"rocell.held_leg_terminal.v1"));}
  for(int mode=0;mode<3;++mode){
    Bus b;Clock c;b.stuck=mode==1;b.bad=mode==2?15:-1;
    HeldElbowLegOwner owner(policy(),2908,2,healthy);HeldLegEvidencePublisher pub;Sink sink;
    assert(pub.begin(sink,"test-boot","test-leg"));
    assert(!pub.begin(sink,"test-boot","test-leg"));
    for(int i=0;i<30;++i){c.tick+=110000;pub.poll(owner,b,c,sink);}
    assert(!pub.faulted()&&owner.terminal());
    for(const auto& r:sink.records)std::cout<<r<<"\n";
    assert(sink.records.size()==owner.scan_count()+(owner.action()?1:0)+1);
  }
  for(int f=0;f<7;++f){
    Bus b;Clock c;HeldElbowLegOwner owner(policy(),2908,2,healthy);
    HeldLegEvidencePublisher pub;Sink sink;sink.fail_at=f;
    assert(pub.begin(sink,"test-boot","test-leg"));
    for(int i=0;i<30;++i){c.tick+=110000;pub.poll(owner,b,c,sink);}
    assert(pub.faulted()&&owner.phase()==HeldLegPhase::Fault);
    int reads=b.reads,writes=b.writes;pub.poll(owner,b,c,sink);
    assert(b.reads==reads&&b.writes==writes&&writes<2);
  }
  {Bus b;Clock c;HeldElbowLegOwner owner(policy(),2908,2,healthy);
   HeldLegEvidencePublisher pub;Sink sink;pub.poll(owner,b,c,sink);
   assert(pub.faulted()&&b.reads==0&&b.writes==0);}
}

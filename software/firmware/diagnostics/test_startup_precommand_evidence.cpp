#include <cassert>
#include "startup_precommand_evidence.h"
#include "evidence_store.h"
struct Clock{uint64_t tick=100;uint64_t now_us(){return ++tick;}};
struct Bus{
 int End=0,Error=0,reads=0;bool torque=true;
 int Read(uint8_t,uint8_t address,uint8_t* bytes,uint8_t width){
  ++reads;if(address==56){bytes[0]=0xd0;bytes[1]=7;}
  if(address==40)bytes[0]=torque?1:0;return width;
 }
};
struct Sink{
 rocell_diag::EvidenceStore<16,2304> store;int calls=0,fail_at=-1;
 bool reserve(size_t n){return store.reserve(n);}
 bool faulted()const{return store.faulted();}
 bool publish(const char* kind,const char* json){if(calls++==fail_at)return false;return store.publish(kind,json);}
};
int main(){using namespace rocell_diag;
 StartupPositionPolicy p={};for(auto& w:p.joints)w={1990,2010};p.drift_tolerance=2;
 p.minimum_separation_us=100000;p.maximum_wait_us=1000000;p.maximum_pair_us=10000;
 p.maximum_scan_us=100000;p.maximum_age_us=100000;
 for(int mode=0;mode<6;++mode){
  Bus bus;Clock clock;Sink sink;if(mode<3)sink.fail_at=mode;if(mode==3)bus.torque=false;
  StartupPrecommandEvidence<Bus,Clock,Sink> evidence(bus,clock,sink,p,0);
  assert(evidence.begin("boot","command",2008,8));assert(bus.reads==0);
  evidence.poll();clock.tick+=100000;evidence.poll();
  if(mode<4){assert(evidence.state()==StartupEvidenceState::Fault);
    assert(!evidence.boundary(2008,clock.now_us()));}
  else{assert(evidence.state()==StartupEvidenceState::Bound&&sink.store.size()==3);
    assert(evidence.boundary(2008,clock.now_us()));
    if(mode==4)assert(!evidence.boundary(2009,clock.now_us()));
    else assert(!evidence.boundary(2008,clock.tick+200000));
    assert(!evidence.boundary(2008,clock.now_us()));}
  const int before=bus.reads;evidence.poll();assert(bus.reads==before);
  assert(!evidence.begin("boot","again",2008,8));
 }
}

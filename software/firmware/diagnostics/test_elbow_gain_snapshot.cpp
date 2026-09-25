#include <cassert>
#include "elbow_gain_snapshot.h"
using namespace rocell_diag;
struct Clock {uint64_t tick=100,step=1;uint64_t now_us(){tick+=step;return tick;}};
// Deliberately no Write, EnableTorque, reset or other mutating API.
struct ReadOnlyBus {
  int End=0,Error=0,calls=0,fail_at=-1,error_at=-1;
  int Read(uint8_t id,uint8_t address,uint8_t* bytes,uint8_t width){
    const uint8_t expected[]={21,22,23};
    assert(id==14&&calls<3&&address==expected[calls]);
    for(int i=0;i<width;++i)bytes[i]=static_cast<uint8_t>(address+i);
    Error=calls==error_at?4:0;return calls++==fail_at?0:width;
  }
};
bool inactive(void* value){return *static_cast<bool*>(value);}
struct Ownership {int checks=0,deny_at=0;};
bool ownership(void* value){
  auto& state=*static_cast<Ownership*>(value);
  return state.checks++!=state.deny_at;
}
struct ScriptClock {
  uint64_t values[6]={100,101,102,103,104,105};int at=0;
  uint64_t now_us(){assert(at<6);return values[at++];}
};
int main(){
  // Loss of ownership at any boundary prevents a complete capture, including
  // loss after the final read. A used snapshot never resumes partial acquisition.
  for(int boundary=0;boundary<4;++boundary){
    ReadOnlyBus bus;Clock clock;Ownership state;state.deny_at=boundary;
    ElbowGainSnapshot snapshot;
    assert(!snapshot.acquire(bus,clock,ownership,&state));
    assert(!snapshot.complete()&&bus.calls==boundary);
    assert(!snapshot.acquire(bus,clock,ownership,&state)&&bus.calls==boundary);
  }
  for(int boundary=0;boundary<6;++boundary){
    ReadOnlyBus bus;ScriptClock clock;bool idle=true;
    clock.values[boundary]=0;ElbowGainSnapshot snapshot;
    assert(!snapshot.acquire(bus,clock,inactive,&idle));
    assert(!snapshot.complete());
  }
  for(int mode=0;mode<2;++mode)for(int failed=-1;failed<3;++failed){
    ReadOnlyBus bus;Clock clock;bool idle=true;ElbowGainSnapshot snapshot;
    if(mode)bus.error_at=failed;else bus.fail_at=failed;
    assert(snapshot.acquire(bus,clock,inactive,&idle)==(failed==-1));
    assert(snapshot.complete()==(failed==-1));
    assert(bus.calls==(failed==-1?3:failed+1));
    if(failed>=0){const auto* r=snapshot.read(failed);assert(r&&r->status==ReadStatus::Failed&&r->bytes[0]==0);}
    const int calls=bus.calls;assert(!snapshot.acquire(bus,clock,inactive,&idle));assert(bus.calls==calls);
  }
  {ReadOnlyBus bus;Clock clock;bool idle=false;ElbowGainSnapshot s;
   assert(!s.acquire(bus,clock,inactive,&idle)&&bus.calls==0);}
  {ReadOnlyBus bus;Clock clock;clock.step=50001;bool idle=true;ElbowGainSnapshot s;
   assert(!s.acquire(bus,clock,inactive,&idle)&&bus.calls==1);}
  {ReadOnlyBus bus;Clock clock;clock.tick=INT64_MAX;bool idle=true;ElbowGainSnapshot s;
   assert(!s.acquire(bus,clock,inactive,&idle)&&bus.calls==0);}
  {ReadOnlyBus bus;bus.End=1;Clock clock;bool idle=true;ElbowGainSnapshot s;
   assert(!s.acquire(bus,clock,inactive,&idle)&&bus.calls==0);}
  return 0;
}

#include <cassert>
#include "elbow_configuration_snapshot.h"
using namespace rocell_diag;
struct Clock {uint64_t tick=100,step=1;uint64_t now_us(){tick+=step;return tick;}};
// Deliberately no Write, EnableTorque, reset or other mutating API.
struct ReadOnlyBus {
  int End=0,Error=0,calls=0,fail_at=-1,error_at=-1;
  int Read(uint8_t id,uint8_t address,uint8_t* bytes,uint8_t width){
    const uint8_t expected[]={3,9,11,26,27,31,33,40,41,46,48,55};
    assert(id==14&&calls<12&&address==expected[calls]);
    for(int i=0;i<width;++i)bytes[i]=static_cast<uint8_t>(address+i);
    Error=calls==error_at?4:0;return calls++==fail_at?0:width;
  }
};
bool inactive(void* value){return *static_cast<bool*>(value);}
int main(){
  for(int mode=0;mode<2;++mode)for(int failed=-1;failed<12;++failed){
    ReadOnlyBus bus;Clock clock;bool idle=true;ElbowConfigurationSnapshot snapshot;
    if(mode)bus.error_at=failed;else bus.fail_at=failed;
    assert(snapshot.acquire(bus,clock,inactive,&idle)==(failed==-1));
    assert(snapshot.complete()==(failed==-1));
    assert(bus.calls==(failed==-1?12:failed+1));
    if(failed>=0){const auto* r=snapshot.read(failed);assert(r&&r->status==ReadStatus::Failed&&r->bytes[0]==0);}
    const int calls=bus.calls;assert(!snapshot.acquire(bus,clock,inactive,&idle));assert(bus.calls==calls);
  }
  {ReadOnlyBus bus;Clock clock;bool idle=false;ElbowConfigurationSnapshot s;
   assert(!s.acquire(bus,clock,inactive,&idle)&&bus.calls==0);}
  {ReadOnlyBus bus;Clock clock;clock.step=50001;bool idle=true;ElbowConfigurationSnapshot s;
   assert(!s.acquire(bus,clock,inactive,&idle)&&bus.calls==1);}
  {ReadOnlyBus bus;Clock clock;clock.tick=INT64_MAX;bool idle=true;ElbowConfigurationSnapshot s;
   assert(!s.acquire(bus,clock,inactive,&idle)&&bus.calls==0);}
  {ReadOnlyBus bus;bus.End=1;Clock clock;bool idle=true;ElbowConfigurationSnapshot s;
   assert(!s.acquire(bus,clock,inactive,&idle)&&bus.calls==0);}
  return 0;
}

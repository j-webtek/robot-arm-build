#include <cassert>
#include <iostream>
#include "shoulder_configuration_snapshot.h"
#include "shoulder_configuration_json.h"
using namespace rocell_diag;
struct Clock {uint64_t tick=100,step=1;uint64_t now_us(){tick+=step;return tick;}};
// Only a Read API: the component cannot call Write or EnableTorque.
struct ReadOnlyBus {
 int End=0,Error=0,calls=0,fail=-1,error=-1;
 int Read(uint8_t id,uint8_t address,uint8_t* bytes,uint8_t width){
  const uint8_t addresses[]={3,9,11,21,22,23,26,27,31,33,40,41,42,46,48,55,56};
  const uint8_t widths[]={2,2,2,1,1,1,1,1,2,1,1,1,2,2,2,1,15};
  assert(calls<34&&id==12+calls/17&&address==addresses[calls%17]&&width==widths[calls%17]);
  for(int i=0;i<width;++i)bytes[i]=42;
  Error=calls==error?4:0;return calls++==fail?0:width;
 }
};
struct Gate {int calls=0,stop=-1;};
bool inactive(void* context){auto& gate=*static_cast<Gate*>(context);return gate.calls++!=gate.stop;}
int main(){
 for(int kind=0;kind<2;++kind)for(int fault=-1;fault<34;++fault){
  ReadOnlyBus bus;Clock clock;Gate gate;ShoulderConfigurationSnapshot s;
  if(kind)bus.error=fault;else bus.fail=fault;
  assert(s.acquire(bus,clock,inactive,&gate)==(fault<0));
  assert(s.complete()==(fault<0));assert(bus.calls==(fault<0?34:fault+1));
  if(fault>=0){const auto* r=s.read(fault);assert(r->status==ReadStatus::Failed);
    for(auto byte:r->bytes)assert(byte==0);}
  int calls=bus.calls;assert(!s.acquire(bus,clock,inactive,&gate));assert(bus.calls==calls);
 }
 for(int stop=0;stop<=34;++stop){
  ReadOnlyBus bus;Clock clock;Gate gate;gate.stop=stop;ShoulderConfigurationSnapshot s;
  assert(!s.acquire(bus,clock,inactive,&gate));assert(bus.calls==stop);assert(!s.complete());
 }
 {ReadOnlyBus bus;Clock clock;Gate gate;clock.step=50001;ShoulderConfigurationSnapshot s;
  assert(!s.acquire(bus,clock,inactive,&gate));assert(bus.calls==1);}
 {ReadOnlyBus bus;Clock clock;Gate gate;clock.step=20000;ShoulderConfigurationSnapshot s;
  assert(!s.acquire(bus,clock,inactive,&gate));assert(bus.calls<34);}
 {ReadOnlyBus bus;Clock clock;Gate gate;bus.End=1;ShoulderConfigurationSnapshot s;
  assert(!s.acquire(bus,clock,inactive,&gate));assert(bus.calls==0);}
 std::cout<<"SHOULDER_READ_ONLY_SCENARIOS_PASSED\n";
 {ReadOnlyBus bus;Clock clock;Gate gate;ShoulderConfigurationSnapshot s;
  assert(s.acquire(bus,clock,inactive,&gate));char output[8192]={};
  assert(shoulder_configuration_json(s,"abababababababababababababababab","shoulder-config-1",output,sizeof(output)));
  char tiny[16]={};assert(!shoulder_configuration_json(s,"abababababababababababababababab","shoulder-config-1",tiny,sizeof(tiny)));
  std::cout<<output<<"\n";}
}

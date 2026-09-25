#define main acquisition_cases
#include "test_elbow_configuration_snapshot.cpp"
#undef main
#include "elbow_configuration_json.h"
#include <iostream>
int main(){
  assert(acquisition_cases()==0);
  for(int fault=-1;fault<12;++fault){
    ReadOnlyBus bus;bus.fail_at=fault;Clock clock;bool idle=true;
    ElbowConfigurationSnapshot snapshot;snapshot.acquire(bus,clock,inactive,&idle);
    char output[4096],tiny[2]={'x',0};
    assert(!elbow_configuration_json(snapshot,"11111111111111111111111111111111","config-1",tiny,sizeof(tiny)));
    assert(tiny[0]==0);
    assert(elbow_configuration_json(snapshot,"11111111111111111111111111111111","config-1",output,sizeof(output)));
    std::cout<<output<<"\n";
  }
}

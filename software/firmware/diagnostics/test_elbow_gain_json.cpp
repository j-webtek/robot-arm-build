#define main acquisition_cases
#include "test_elbow_gain_snapshot.cpp"
#undef main
#include "elbow_gain_json.h"
#include <iostream>
int main(){
  assert(acquisition_cases()==0);
  for(int fault=-1;fault<3;++fault){
    ReadOnlyBus bus;bus.fail_at=fault;Clock clock;bool idle=true;
    ElbowGainSnapshot snapshot;snapshot.acquire(bus,clock,inactive,&idle);
    char output[4096],tiny[2]={'x',0};
    assert(!elbow_gain_json(snapshot,"11111111111111111111111111111111","config-1",tiny,sizeof(tiny)));
    assert(tiny[0]==0);
    assert(elbow_gain_json(snapshot,"11111111111111111111111111111111","config-1",output,sizeof(output)));
    std::cout<<output<<"\n";
  }
}

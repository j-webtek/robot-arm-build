#define main prior_leg_tests
#include "test_held_elbow_leg_owner.cpp"
#undef main
#include "pose_observation_sequence.h"
#include "pose_observation_json.h"
#include <iostream>
// Compilation fails if the new component attempts the existing motion method.
struct ReadOnlyBus:Bus {int WritePosEx(uint8_t,int16_t,uint16_t,uint8_t)=delete;};
int main(){
  using Sequence=rocell_diag::PoseObservationSequence;
  for(int fault=-1;fault<84;++fault){
    ReadOnlyBus bus;Clock clock;Sequence sequence;bus.bad=fault;
    assert(sequence.begin(clock.tick));assert(!sequence.begin(clock.tick));
    for(int i=0;i<12;++i){clock.tick+=110000;sequence.poll(bus,clock);}
    assert(sequence.state()==(fault<0?Sequence::State::Captured:Sequence::State::Fault));
    assert(bus.writes==0&&bus.reads<=84);
    if(fault<0){
      char record[4096],tiny[2];
      for(size_t i=0;i<=sequence.size();++i){
        assert(!pose_observation_record(sequence,i,"test-boot","test-pose",tiny,sizeof(tiny)));
        assert(pose_observation_record(sequence,i,"test-boot","test-pose",record,sizeof(record)));
        std::cout<<record<<"\n";
      }
    }
    const int reads=bus.reads;sequence.poll(bus,clock);assert(bus.reads==reads);
    assert(!sequence.begin(clock.tick));
  }
  {ReadOnlyBus bus;Clock clock;Sequence sequence;sequence.begin(clock.tick);
   clock.tick+=1000001;sequence.poll(bus,clock);
   assert(sequence.state()==Sequence::State::Fault&&bus.reads==0);}
  {ReadOnlyBus bus;Clock clock;Sequence sequence;sequence.begin(1000);
   sequence.poll(bus,clock);assert(sequence.state()==Sequence::State::Fault&&bus.reads==0);}
  return 0;
}

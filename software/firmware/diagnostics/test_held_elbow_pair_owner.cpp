#define main run_leg_tests
#include "test_held_elbow_leg_owner.cpp"
#undef main
#include "held_elbow_pair_owner.h"
#include <iostream>
struct Driver {
  Bus& bus;Clock& clock;bool export_failure=false;
  void poll(HeldElbowLegOwner& leg){
    clock.tick+=110000;leg.poll(bus,clock);
    if(export_failure)leg.export_failed();
  }
};
// Synthetic admission only: production must supply signature/export validation.
struct Admission {
  bool accept=true;int calls=0;
  uint16_t expected_anchor=2902;
  bool consume(uint16_t anchor,const HeldElbowLegOwner& leg){
    ++calls;assert(anchor==expected_anchor&&leg.phase()==HeldLegPhase::Arrived);
    assert(leg.action()&&leg.scan_count()>=5);return accept;
  }
};
void run_pair(HeldElbowPairOwner& pair,Driver& driver){for(int i=0;i<30;++i)pair.poll(driver);}
int run_pair_cases(){
  assert(run_leg_tests()==0);
  // Proposed +12 experiment, using the actual narrow elbow envelope. The bus
  // is synthetic: these assertions establish protocol behavior, not accuracy.
  for(int anchor=2893;anchor<=2898;++anchor)for(int fault=0;fault<4;++fault){
    Bus bus;Clock clock;auto p=policy();
    p.minimum[3]=2893;p.maximum[3]=2909;
    bus.pos[3]=bus.goal[3]=anchor;
    HoldStateSnapshot held;assert(held.capture(bus,clock,p.pair_us,p.scan_us));
    HeldElbowPairOwner pair(p,12,2,healthy);Driver driver{bus,clock};
    Admission admission;admission.expected_anchor=anchor;
    const bool started=pair.start(held);
    if(anchor==2898){assert(!started&&bus.writes==0);continue;}
    assert(started);
    if(fault==1)bus.stuck=true;
    if(fault==2)bus.lost=true;
    if(fault==3)driver.export_failure=true;
    run_pair(pair,driver);
    if(fault){
      assert(pair.phase()==HeldPairPhase::Stopped);
      assert(!pair.admit_return(admission)&&admission.calls==0);
    }else{
      assert(pair.phase()==HeldPairPhase::AwaitingExport);
      assert(bus.pos[3]==unsigned(anchor+12)&&bus.writes==1);
      run_pair(pair,driver);assert(bus.writes==1);
      assert(pair.admit_return(admission));run_pair(pair,driver);
      assert(pair.phase()==HeldPairPhase::Complete&&bus.writes==2);
      assert(bus.pos[3]==unsigned(anchor)&&bus.goal[3]==unsigned(anchor));
    }
    const int writes=bus.writes;run_pair(pair,driver);assert(bus.writes==writes);
  }
  for(int direction:{-1,1})for(int fault=0;fault<8;++fault){
    Bus bus;Clock clock;HoldStateSnapshot held;auto p=policy();
    assert(held.capture(bus,clock,p.pair_us,p.scan_us));
    bool ok=true;HeldElbowPairOwner pair(p,6*direction,2,healthy,&ok);
    Driver driver{bus,clock};Admission admission;
    assert(pair.start(held));assert(!pair.start(held));
    assert(!pair.admit_return(admission)&&admission.calls==0);
    if(fault==1)bus.stuck=true;
    if(fault==2)bus.lost=true;
    if(fault==3)driver.export_failure=true;
    run_pair(pair,driver);
    if(fault>=1&&fault<=3){
      assert(pair.phase()==HeldPairPhase::Stopped);
      assert(!pair.admit_return(admission)&&admission.calls==0);
    }else{
      assert(pair.phase()==HeldPairPhase::AwaitingExport&&bus.writes==1);
      const int reads=bus.reads;run_pair(pair,driver);
      assert(bus.reads==reads&&bus.writes==1); // No timed automatic return.
      if(fault==4)admission.accept=false;
      if(fault==5)bus.pos[1]+=3;
      if(fault==6)ok=false;
      const bool accepted=pair.admit_return(admission);
      assert(accepted==(fault!=4&&fault!=6));
      assert(!pair.admit_return(admission));
      if(fault==7)driver.export_failure=true;
      run_pair(pair,driver);
      if(fault==0){
        assert(pair.phase()==HeldPairPhase::Complete&&bus.writes==2);
        assert(bus.pos[3]==2902&&bus.goal[3]==2902&&pair.original_anchor()==2902);
        assert(pair.leg()->action()->bytes[1]==(2902&255));
      }else{assert(pair.phase()==HeldPairPhase::Stopped&&bus.writes==1);}
    }
    const int reads=bus.reads,writes=bus.writes;run_pair(pair,driver);
    assert(bus.reads==reads&&bus.writes==writes);
  }
  {Bus bus;Clock clock;HoldStateSnapshot held;auto p=policy();
   assert(held.capture(bus,clock,p.pair_us,p.scan_us));
   for(int offset:{0,4,17,-17}){
     HeldElbowPairOwner pair(p,offset,2,healthy);assert(!pair.start(held));
     Driver driver{bus,clock};run_pair(pair,driver);assert(bus.writes==0);
   }}
  // Host ABI sizes are a regression indicator, not an ESP32 heap measurement.
  assert(sizeof(HeldElbowPairOwner)<sizeof(HeldElbowLegOwner)+sizeof(HoldStateSnapshot)+512);
  std::cout<<"pair_bytes="<<sizeof(HeldElbowPairOwner)
           <<" leg_bytes="<<sizeof(HeldElbowLegOwner)<<"\n";
  return 0;
}
#ifndef HELD_PAIR_NO_MAIN
int main(){return run_pair_cases();}
#endif

// Offline exact-policy recovery and finite pair checks. No device adapters.
#define HELD_PAIR_NO_MAIN
#include "test_held_elbow_pair_owner.cpp"
#include "controller_hold_config.h"
#include <fstream>
#include <iterator>
struct ObservedBus:Bus {
  int EnableTorque(uint8_t,uint8_t){assert(false);return 0;}
  ObservedBus(){
    const unsigned observed[7]={2047,2487,1629,2899,2035,2041,2054};
    for(int i=0;i<7;++i)pos[i]=observed[i];
    goal[3]=2903;
  }
};
int main(int argc,char** argv){
  assert(argc==2);std::ifstream input(argv[1],std::ios::binary);
  std::string raw((std::istreambuf_iterator<char>(input)),{});
  ControllerHoldConfigParser parser;assert(parser.parse(raw.data(),raw.size()));
  auto p=parser.get()->policy;assert(!p.permit_explicit_enable);
  // Ordinary hold cannot silently reinterpret the observed four-count error.
  {ObservedBus bus;Clock clock;HoldInitializationOwner ordinary(p);
   for(int i=0;i<10;++i){clock.tick+=110000;ordinary.poll(bus,clock);}
   assert(ordinary.phase()==HoldPhase::Fault&&bus.writes==0);}
  for(int fault=0;fault<8;++fault){
    ObservedBus bus;Clock clock;
    HoldInitializationOwner recovery(p,SixCountRecoveryAdmission{});
    for(int i=0;i<10;++i){clock.tick+=110000;recovery.poll(bus,clock);}
    assert(recovery.phase()==HoldPhase::Captured&&bus.writes==1);
    assert(bus.pos[3]==2899&&bus.goal[3]==2899);
    // Production must export recovery and obtain a separately authorized startup
    // and ordinary hold. This fixture checks owners, not that lifecycle approval.
    HoldInitializationOwner ordinary(p);
    for(int i=0;i<10;++i){clock.tick+=110000;ordinary.poll(bus,clock);}
    assert(ordinary.phase()==HoldPhase::Captured&&bus.writes==2);
    HoldStateSnapshot held;assert(held.capture(bus,clock,p.pair_us,p.scan_us));
    HeldElbowPairOwner pair(p,10,2,healthy);Driver driver{bus,clock};
    Admission admission;admission.expected_anchor=2899;
    assert(pair.start(held));assert(!pair.start(held));
    if(fault==1)bus.stuck=true;
    if(fault==2)bus.lost=true;
    if(fault==3)driver.export_failure=true;
    if(fault==4)bus.pos[1]+=3;
    run_pair(pair,driver);
    if(fault>=1&&fault<=4){
      assert(pair.phase()==HeldPairPhase::Stopped);
      assert(!pair.admit_return(admission)&&admission.calls==0);
      assert(bus.writes<=3);
    }else{
      assert(pair.phase()==HeldPairPhase::AwaitingExport&&bus.writes==3);
      assert(bus.pos[3]==2909&&bus.goal[3]==2909);
      const int reads=bus.reads;run_pair(pair,driver);
      assert(bus.reads==reads&&bus.writes==3); // No timed return.
      if(fault==5)admission.accept=false;
      if(fault==6)bus.pos[1]+=3;
      assert(pair.admit_return(admission)==(fault!=5));
      if(fault==7)bus.stuck=true;
      run_pair(pair,driver);
      if(fault==0){
        assert(pair.phase()==HeldPairPhase::Complete&&bus.writes==4);
        assert(bus.pos[3]==2899&&bus.goal[3]==2899);
      }else{
        assert(pair.phase()==HeldPairPhase::Stopped);
        assert(bus.writes==(fault==7?4:3));
      }
    }
    const int reads=bus.reads,writes=bus.writes;
    run_pair(pair,driver);assert(bus.reads==reads&&bus.writes==writes);
  }
  // A one-count change to the anchor invalidates +10: no clipping or recenter.
  {ObservedBus bus;Clock clock;bus.pos[3]=bus.goal[3]=2900;
   HoldStateSnapshot held;assert(held.capture(bus,clock,p.pair_us,p.scan_us));
   HeldElbowPairOwner pair(p,10,2,healthy);assert(!pair.start(held));
   assert(bus.writes==0);}
  std::cout<<"OBSERVED_POSE_CORE_SCENARIOS_PASSED\n";
}

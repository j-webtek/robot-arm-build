#define main prior_leg_tests
#include "test_held_elbow_leg_owner.cpp"
#undef main
#include "pose_observation_owner.h"
struct ReadOnlyBus:Bus {int WritePosEx(uint8_t,int16_t,uint16_t,uint8_t)=delete;};
struct Reservation {
  bool available=true;int calls=0;
  static bool reserve(void* p){auto& r=*static_cast<Reservation*>(p);++r.calls;
    const bool allowed=r.available;r.available=false;return allowed;}
};
int main(){
  for(bool allowed:{false,true}){
    ReadOnlyBus bus;Clock clock;Reservation gate;gate.available=allowed;
    PoseObservationOwner<ReadOnlyBus,Clock> owner(bus,clock,Reservation::reserve,&gate,"test-boot");
    assert(!owner.request("wrong-boot","scan")&&gate.calls==0);
    assert(owner.request("test-boot","scan")==allowed);
    assert(bus.reads==0&&bus.writes==0); // HTTP admission must be non-acquiring.
    assert(!owner.request("test-boot","scan")&&gate.calls==1);
    assert(!Reservation::reserve(&gate)); // No release after completion.
    assert(owner.record(0)==nullptr);
    for(int i=0;i<10;++i){clock.tick+=110000;owner.poll();}
    assert(!owner.active()&&owner.size()==(allowed?4:0));
    assert(bus.reads==(allowed?84:0)&&bus.writes==0);
    assert(!owner.export_fault());
    if(allowed){for(size_t i=0;i<owner.size();++i)assert(owner.record(i));}
    assert(owner.record(4)==nullptr);
    const int reads=bus.reads;owner.poll();assert(bus.reads==reads);
  }
  {ReadOnlyBus bus;Clock clock;Reservation gate;bus.bad=4;
   PoseObservationOwner<ReadOnlyBus,Clock> owner(bus,clock,Reservation::reserve,&gate,"test-boot");
   assert(owner.request("test-boot","scan"));owner.poll();
   assert(!owner.active()&&owner.size()==2&&bus.writes==0);
   assert(strstr(owner.record(1),"FAULT"));}
}

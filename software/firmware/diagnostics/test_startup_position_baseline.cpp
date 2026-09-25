#include <cassert>
#include <cstring>
#include <initializer_list>
#include "startup_position_baseline.h"
struct Clock{uint64_t tick=100;uint64_t now_us(){return ++tick;}};
struct Bus{
 int End=0,Error=0,reads=0,change=0;bool moving=false,goal=false,failed=false;
 int Read(uint8_t,uint8_t address,uint8_t* bytes,uint8_t width){
   ++reads;if(failed)return 0;
   unsigned value=address==42?(goal?2000:0):2000+change;
   bytes[0]=value&255;bytes[1]=value>>8;
   if(width==15)bytes[10]=moving?1:0;return width;
 }
};
rocell_diag::StartupPositionPolicy policy(){
 rocell_diag::StartupPositionPolicy p={};for(auto& w:p.joints)w={1980,2020};
 p.drift_tolerance=2;p.minimum_separation_us=100000;p.maximum_wait_us=1000000;
 p.maximum_pair_us=1000;p.maximum_scan_us=10000;p.maximum_age_us=100000;return p;
}
int main(){using namespace rocell_diag;
 {Bus bus;Clock clock;StartupPositionBaseline gate(policy());gate.poll(bus,clock);
  assert(gate.state()==StartupPositionState::Waiting&&bus.reads==14);
  gate.poll(bus,clock);assert(bus.reads==14);clock.tick+=100000;gate.poll(bus,clock);
  assert(gate.state()==StartupPositionState::Observed&&bus.reads==28);
  assert(gate.scan(0)&&gate.scan(1)&&!gate.scan(2));
  assert(gate.fresh(clock.now_us()));gate.poll(bus,clock);assert(bus.reads==28);
  assert(gate.bind_elbow_target(2008,8,clock.now_us())&&gate.bound_target()==2008);
  assert(!gate.bind_elbow_target(2008,8,clock.now_us()));
  assert(!gate.fresh(clock.tick+200000));assert(!gate.fresh(clock.now_us()));}
 for(int mode=0;mode<6;++mode){Bus bus;Clock clock;StartupPositionBaseline gate(policy());
  gate.poll(bus,clock);clock.tick+=100000;
  if(mode==0)bus.goal=true;if(mode==1)bus.moving=true;if(mode==2)bus.failed=true;
  if(mode==3)bus.change=3;if(mode==4)bus.change=30;if(mode==5)clock.tick+=2000000;
  gate.poll(bus,clock);assert(gate.state()==StartupPositionState::Fault);
  const int before=bus.reads;gate.poll(bus,clock);assert(bus.reads==before);assert(!gate.fresh(clock.now_us()));}
 {Bus bus;Clock clock;auto p=policy();p.minimum_separation_us=0;StartupPositionBaseline gate(p);
  gate.poll(bus,clock);assert(gate.state()==StartupPositionState::Fault&&bus.reads==0);}
 {Bus bus;Clock clock;StartupPositionBaseline gate(policy());gate.poll(bus,clock);
  clock.tick=1;gate.poll(bus,clock);assert(gate.state()==StartupPositionState::Fault&&bus.reads==14);}
 for(unsigned target:{0u,1991u,2009u,2021u}){
  Bus bus;Clock clock;StartupPositionBaseline gate(policy());gate.poll(bus,clock);
  clock.tick+=100000;gate.poll(bus,clock);
  assert(!gate.bind_elbow_target(target,8,clock.now_us()));assert(gate.bound_target()==0);
  assert(!gate.bind_elbow_target(2000,8,clock.now_us()));}
}

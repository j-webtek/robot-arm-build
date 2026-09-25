#include <cassert>
#include <cstring>
#include <initializer_list>
#include "hold_state_snapshot.h"
struct Clock {uint64_t tick=100;uint64_t now_us(){return ++tick;}};
struct AdjacentClock {int calls=0,rewind_at=-1;
 uint64_t now_us(){int n=calls++;return 100+(n+1)/2-(n==rewind_at?1:0);}};
struct Bus {
  int End=0,Error=0,calls=0,bad=-1,device_error=-1;
  uint8_t torque=0;bool nonzero=false;
  int Read(uint8_t id,uint8_t address,uint8_t* out,uint8_t width){
    const int n=calls++;
    Error=n==device_error?1:0;
    assert(id==11+(n<14?n/2:(n-14)/2));
    assert(address==(n<14?(n%2?56:42):(n%2?40:33)));
    assert(width==(n<14?(n%2?15:2):1));
    std::memset(out,0,width);
    if(address==56){out[0]=0xa3;out[1]=0x0a;}
    if(address==42&&nonzero){out[0]=0xa3;out[1]=0x0a;}
    if(address==40)out[0]=torque;
    return n==bad?0:width;
  }
};
int main(){using namespace rocell_diag;
  {Bus bus;AdjacentClock clock;HoldStateSnapshot scan;
   assert(scan.capture(bus,clock,10000,100000)&&bus.calls==28);
   assert(scan.controls().read(0)->started_us==scan.positions().pair(6)->feedback.finished_us);
   assert(scan.fresh(clock.now_us(),250000));}
  // Reject reversal at target/feedback, joint, and scan-type boundaries.
  for(int boundary:{2,4,28,44}){Bus bus;AdjacentClock clock;clock.rewind_at=boundary;
   HoldStateSnapshot scan;assert(!scan.capture(bus,clock,10000,100000));
   int calls=bus.calls;assert(!scan.capture(bus,clock,10000,100000)&&bus.calls==calls);}
  for(int torque=0;torque<=1;++torque){
    Bus bus;bus.torque=torque;bus.nonzero=torque;Clock clock;HoldStateSnapshot scan;
    assert(scan.capture(bus,clock,10000,100000)&&bus.calls==28);
    assert(scan.fresh(clock.now_us(),250000));
    for(size_t i=0;i<7;++i){
      assert(scan.joint(i)->position==2723);
      assert(scan.joint(i)->goal==(torque?2723:0));
      assert(scan.joint(i)->torque==torque);
    }
    assert(!scan.capture(bus,clock,10000,100000)&&bus.calls==28);
    assert(!scan.fresh(clock.tick+300000,250000));
    assert(!scan.fresh(clock.now_us(),250000));
  }
  for(int failure=0;failure<28;++failure){
    for(bool error:{false,true}){
      Bus bus;if(error)bus.device_error=failure;else bus.bad=failure;
      Clock clock;HoldStateSnapshot scan;
      assert(!scan.capture(bus,clock,10000,100000));
      assert(scan.joint(0)==nullptr);
      assert(!scan.fresh(clock.now_us(),250000));
      int calls=bus.calls;assert(!scan.capture(bus,clock,10000,100000));
      assert(bus.calls==calls);
    }
  }
  {Bus bus;bus.End=1;Clock clock;HoldStateSnapshot scan;
   assert(!scan.capture(bus,clock,10000,100000)&&bus.calls==0);}
  {Bus bus;bus.torque=128;Clock clock;HoldStateSnapshot scan;
   assert(!scan.capture(bus,clock,10000,100000));}
  {Bus bus;Clock clock;HoldStateSnapshot scan;
   assert(!scan.capture(bus,clock,10000,40));}
}

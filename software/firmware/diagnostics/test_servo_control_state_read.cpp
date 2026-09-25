#include <cassert>
#include "servo_control_state_read.h"
struct Clock{uint64_t tick=100;uint64_t now_us(){return ++tick;}};
// Consecutive synchronous calls can share an integer-microsecond boundary.
// A read still consumes time; only the gap between calls rounds to zero.
struct AdjacentClock{int calls=0;bool rewind=false;
 uint64_t now_us(){int n=calls++;return 100+(n+1)/2-(rewind&&n==16?1:0);}};
struct Bus{
 int End=0,Error=0,calls=0,bad=-1;bool torque=true;
 int Read(uint8_t id,uint8_t address,uint8_t* raw,uint8_t width){
   assert(width==1&&id==11+calls/2&&address==(calls%2?40:33));
   if(calls++==bad)return 0;
   raw[0]=address==40&&torque?1:0;return 1;
 }
};
int main(){using namespace rocell_diag;
 {Bus bus;AdjacentClock clock;ServoControlStateRead read;
  assert(read.acquire(bus,clock)&&bus.calls==14);
  assert(read.read(8)->started_us==read.read(7)->finished_us);
  assert(read.matches(0,clock.now_us(),100000));}
 {Bus bus;AdjacentClock clock;clock.rewind=true;ServoControlStateRead read;
  assert(!read.acquire(bus,clock)&&bus.calls==9);
  assert(read.read(8)->status==ReadStatus::Failed);
  assert(!read.acquire(bus,clock)&&bus.calls==9);}
 {Bus bus;Clock clock;ServoControlStateRead read;
  assert(read.acquire(bus,clock)&&bus.calls==14&&read.matches(0,clock.now_us(),100000));
  assert(!read.acquire(bus,clock)&&bus.calls==14);
  assert(!read.matches(0,clock.tick+200000,100000));assert(!read.matches(0,clock.now_us(),100000));}
 for(int index=0;index<14;++index){Bus bus;Clock clock;bus.bad=index;ServoControlStateRead read;
  assert(!read.acquire(bus,clock)&&bus.calls==index+1);
  assert(read.read(index)->status==ReadStatus::Failed);
  assert(!read.matches(0,clock.now_us(),100000));}
 {Bus bus;Clock clock;bus.torque=false;ServoControlStateRead read;
  assert(read.acquire(bus,clock));assert(!read.matches(0,clock.now_us(),100000));}
 {Bus bus;Clock clock;ServoControlStateRead read;
  assert(read.acquire(bus,clock));assert(!read.matches(1,clock.now_us(),100000));}
}

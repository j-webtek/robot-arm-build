#include "shoulder_fault_settling_capture.h"
#include <cassert>
#include <cstring>
#include <iostream>
using namespace rocell_diag;
struct Clock {uint64_t tick=1;uint64_t now_us(){return tick+=100;}};
// Deliberately no write methods: any actuator write fails compilation.
struct ReadOnlyBus {
 int End=0,Error=0,reads=0,fail_read=-1;bool moving=false;
 int position=2429,goal=2419,torque=1;
 int Read(uint8_t,uint8_t address,uint8_t* bytes,uint8_t width){
   if(reads++==fail_read)return 0;
   std::memset(bytes,0,width);
   int value=address==56?position:address==42?goal:address==40?torque:0;
   bytes[0]=value&255;if(width>=2)bytes[1]=value>>8;
   if(address==56&&moving)bytes[2]=1;
   return width;
 }
};
int main(){
 auto admitted=[](){return true;};
 for(int mode=0;mode<9;++mode){
   ShoulderFaultSettlingCapture capture;ReadOnlyBus bus;Clock clock;
   assert(capture.begin(1,true,true));assert(!capture.begin(1,true,true));
   for(int step=0;step<12;++step){
     clock.tick+=500000;
     if(mode==1)bus.moving=true;
     if(mode==2&&step==1)bus.goal++;
     if(mode==3&&step==1)bus.torque=0;
     if(mode==4&&step==1)clock.tick=1;
     if(mode==5&&step==1)clock.tick=9000000;
     if(mode==6)bus.position++; // Slow drift must not look settled.
     capture.advance(bus,clock,admitted);
     if(capture.state()==SettlingState::Failed)break;
     assert(capture.state()==SettlingState::WaitingExport);
     int reads=bus.reads;capture.advance(bus,clock,admitted);assert(bus.reads==reads);
     bool valid=capture.exported(mode==7?99:step,mode!=8,clock.now_us());
     if(!valid||capture.state()==SettlingState::Settled)break;
   }
   assert(capture.state()==(mode==0?SettlingState::Settled:
     (mode==1||mode==6)?SettlingState::Exhausted:SettlingState::Failed));
   int reads=bus.reads;capture.advance(bus,clock,admitted);assert(bus.reads==reads);
   if(mode==0)assert(capture.record().position[0]-capture.record().goal[0]==10);
 }
 for(int failure=0;failure<28;++failure){
   ShoulderFaultSettlingCapture capture;ReadOnlyBus bus;Clock clock;bus.fail_read=failure;
   assert(capture.begin(1,true,true));capture.advance(bus,clock,admitted);
   assert(capture.state()==SettlingState::Failed&&bus.reads==failure+1);
   capture.advance(bus,clock,admitted);assert(bus.reads==failure+1);
 }
 {
   ShoulderFaultSettlingCapture capture;ReadOnlyBus bus;Clock clock;
   assert(capture.begin(1,true,true));capture.advance(bus,clock,admitted);
   assert(!capture.exported(0,true,9000001));
   assert(capture.state()==SettlingState::Failed);
 }
 for(int mode=0;mode<3;++mode){
   ShoulderFaultSettlingCapture capture;ReadOnlyBus bus;Clock clock;
   if(mode<2)assert(!capture.begin(1,mode!=0,mode!=1));
   else {assert(capture.begin(1,true,true));auto denied=[](){return false;};capture.advance(bus,clock,denied);}
   assert(capture.state()==SettlingState::Failed&&bus.reads==0);
 }
 std::cout<<"FAULT_SETTLING_OFFLINE_PASSED\n";
}

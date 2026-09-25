#include "shoulder_preload_candidate.h"
#include <cassert>
#include <iostream>
#include <string>
struct Clock {uint64_t tick=1;uint64_t now_us(){return tick+=100;}};
struct Bus {
 int End=0,Error=0,writes=0,reads=0,fail_read=-1,fail_write=0;
 bool wrong_goal=false,neighbor_drift=false,enable_fault=false;
 void syncWrite(uint8_t*,uint8_t,uint8_t,uint8_t*,uint8_t){assert(false&&"Preload must not enable");}
 void SyncWritePosEx(uint8_t*,uint8_t,int16_t*,uint16_t*,uint8_t*){assert(false&&"Preload must not move pair");}
 uint16_t position[7]={2047,2455,1659,2906,1589,2040,2047};
 uint16_t goal[7]={0,0,0,2907,0,0,0};uint8_t torque[7]={0,0,0,1,0,0,0};
 int Read(uint8_t sid,uint8_t address,uint8_t* bytes,uint8_t width){
   if(reads++==fail_read)return 0;
   unsigned i=sid-11,value=0;
   if(address==40)value=torque[i];
   if(address==42)value=goal[i];
   if(address==56)value=position[i];
   for(int j=0;j<width;++j)bytes[j]=0;
   bytes[0]=value&255;if(width>=2)bytes[1]=value>>8;return width;
 }
 int WritePosEx(uint8_t sid,int16_t target,uint16_t speed,uint8_t acc){
   assert(sid==12+writes&&speed==20&&acc==1);
   assert(target==position[sid-11]);++writes;
   goal[sid-11]=wrong_goal?0:target;
   if(neighbor_drift)position[4]+=3;
   if(enable_fault)torque[sid-11]=1;
   return writes==fail_write?0:1;
 }
};
struct Evidence {
 int calls=0,fail=-1;bool operator()(const char*,const rocell_diag::ShoulderPreloadPose&,int,int){return calls++!=fail;}
};
int main(){
 auto admit=[](){return true;};
 {
   Bus bus;Clock clock;Evidence evidence;rocell_diag::ShoulderPreloadCandidate owner;
   assert(owner.run(bus,clock,evidence,admit));assert(bus.writes==2);
   assert(bus.goal[1]==2455&&bus.goal[2]==1659&&bus.torque[1]==0&&bus.torque[2]==0);
   assert(!owner.run(bus,clock,evidence,admit)&&bus.writes==2);
 }
 // Each of the seven full scans has 28 reads; any failed read terminates.
 for(int fault=0;fault<2;++fault){
   Bus bus;if(fault==0)bus.torque[1]=1;else bus.goal[3]=2800;
   Clock clock;Evidence evidence;rocell_diag::ShoulderPreloadCandidate owner;
   assert(!owner.run(bus,clock,evidence,admit)&&bus.writes==0);
 }
 for(int failure=0;failure<196;++failure){
   Bus bus;bus.fail_read=failure;Clock clock;Evidence evidence;rocell_diag::ShoulderPreloadCandidate owner;
   assert(!owner.run(bus,clock,evidence,admit));
   assert(bus.reads==failure+1);
   assert(bus.writes==(failure<84?0:failure<168?1:2));
 }
 for(int failure=0;failure<7;++failure){
   Bus bus;Clock clock;Evidence evidence;evidence.fail=failure;rocell_diag::ShoulderPreloadCandidate owner;
   assert(!owner.run(bus,clock,evidence,admit));assert(evidence.calls==failure+1);
   assert(bus.writes==(failure<2?0:failure<5?1:2));
 }
 for(int fault=0;fault<4;++fault){
   Bus bus;bus.fail_write=fault==0?1:0;bus.wrong_goal=fault==1;
   bus.neighbor_drift=fault==2;bus.enable_fault=fault==3;
   Clock clock;Evidence evidence;rocell_diag::ShoulderPreloadCandidate owner;
   assert(!owner.run(bus,clock,evidence,admit)&&bus.writes==1);
 }
 std::cout<<"SHOULDER_PRELOAD_OFFLINE_PASSED\n";
}

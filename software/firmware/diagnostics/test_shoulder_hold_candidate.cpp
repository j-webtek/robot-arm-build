#define main preload_cases
#include "test_shoulder_preload_candidate.cpp"
#undef main
#include "shoulder_hold_candidate.h"
struct HoldBus:Bus {
 int broadcasts=0,fault=0;
 bool speed_fault=false;
 int Read(uint8_t sid,uint8_t address,uint8_t* bytes,uint8_t width){
   int result=Bus::Read(sid,address,bytes,width);
   if(result==width&&address==56){
     bytes[6]=122;bytes[7]=27; // Raw voltage/temperature evidence, not limits.
     if(speed_fault&&sid==12)bytes[2]=1;
   }
   return result;
 }
 void syncWrite(uint8_t* ids,uint8_t count,uint8_t address,uint8_t* values,uint8_t width){
   assert(count==2&&ids[0]==12&&ids[1]==13&&address==40&&width==1);
   assert(values[0]==1&&values[1]==1&&goal[1]==position[1]&&goal[2]==position[2]);
   ++broadcasts;
   if(fault==1)return; // dropped broadcast
   torque[1]=1;if(fault!=2)torque[2]=1;
   if(fault==3)position[4]+=3;
   if(fault==4)goal[1]=0;
 }
};
int main(){
 auto admit=[](){return true;};
 for(int fault=0;fault<5;++fault){
   HoldBus bus;bus.fault=fault;Clock clock;Evidence evidence;rocell_diag::ShoulderHoldCandidate owner;
   assert(owner.run(bus,clock,evidence,admit)==(fault==0));
   assert(bus.writes==2&&bus.broadcasts==1);
   assert(owner.delivery()==rocell_diag::ShoulderEnableDelivery::SentUnacknowledged);
   assert(!owner.run(bus,clock,evidence,admit));assert(bus.broadcasts==1&&bus.writes==2);
 }
 // All read failures, including the final post-enable sample, stop progression.
 for(int failure=0;failure<336;++failure){
   HoldBus bus;bus.fail_read=failure;Clock clock;Evidence evidence;rocell_diag::ShoulderHoldCandidate owner;
   assert(!owner.run(bus,clock,evidence,admit));assert(bus.reads==failure+1);
   assert(bus.broadcasts==(failure>=252?1:0));
 }
 for(int failure=0;failure<12;++failure){
   HoldBus bus;Clock clock;Evidence evidence;evidence.fail=failure;rocell_diag::ShoulderHoldCandidate owner;
   assert(!owner.run(bus,clock,evidence,admit));assert(evidence.calls==failure+1);
   assert(bus.broadcasts==(failure>=8?1:0));
 }
 // Intent export can race physical drift: fresh reread must prevent enable.
 {
   HoldBus bus;Clock clock;rocell_diag::ShoulderHoldCandidate owner;
   auto evidence=[&](const char* event,const rocell_diag::ShoulderPreloadPose&,int,int){
     if(std::string(event)=="PAIR_ENABLE_INTENT")bus.position[1]+=3;
     return true;
   };
   assert(!owner.run(bus,clock,evidence,admit));assert(bus.broadcasts==0&&bus.writes==2);
 }
 {
   HoldBus bus;Clock clock;rocell_diag::ShoulderHoldCandidate owner;bool allowed=true;
   auto gate=[&](){return allowed;};
   auto evidence=[&](const char* event,const rocell_diag::ShoulderPreloadPose&,int,int){
     if(std::string(event)=="PAIR_ENABLE_INTENT")allowed=false;
     return true;
   };
   assert(!owner.run(bus,clock,evidence,gate));assert(bus.broadcasts==0&&bus.writes==2);
 }
 // Timed observation is separate from initial readback and never writes again.
 for(int fault=0;fault<7;++fault){
   HoldBus bus;Clock clock;Evidence evidence;rocell_diag::ShoulderHoldCandidate owner;
   assert(owner.run(bus,clock,evidence,admit));assert(!owner.observation_complete());
   for(int sample=0;sample<24&&!owner.observation_complete();++sample){
     clock.tick+=100000;
     if(sample==3){
       if(fault==1)bus.position[1]+=3;
       if(fault==2)bus.torque[2]=0;
       if(fault==3)bus.speed_fault=true;
       if(fault==4)clock.tick+=600000;
       if(fault==5)bus.fail_read=bus.reads;
       if(fault==6)evidence.fail=evidence.calls;
     }
     owner.poll(bus,clock,evidence,admit);
   }
   assert(owner.observation_complete()==(fault==0));
   assert(bus.writes==2&&bus.broadcasts==1);
   const int reads=bus.reads;
   owner.poll(bus,clock,evidence,admit);assert(bus.reads==reads);
 }
 std::cout<<"SHOULDER_HOLD_OFFLINE_PASSED\n";
}

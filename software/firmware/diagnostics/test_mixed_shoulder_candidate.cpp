#define main preload_test_main
#include "test_shoulder_preload_candidate.cpp"
#undef main
#include "mixed_shoulder_candidate.h"
#include "shoulder_hold_event_json.h"
struct MixedBus:Bus {
 int fault=0;
 MixedBus(){torque[1]=1;goal[1]=position[1];}
 int WritePosEx(uint8_t sid,int16_t target,uint16_t speed,uint8_t acc){
   assert(sid==13&&target==1659&&speed==20&&acc==1);++writes;
   goal[2]=fault==2?0:target;
   if(fault==1)torque[2]=1;
   if(fault==3)position[4]+=3;
   return fault==4?0:1;
 }
};
int main(){
 auto admit=[](){return true;};
 for(int fault=0;fault<8;++fault){
   MixedBus bus;bus.fault=fault;Clock clock;rocell_diag::MixedShoulderCandidate owner;
   unsigned sequence=0;
   auto evidence=[&](const char* event,const rocell_diag::ShoulderPreloadPose& pose,int sid,int result){
     char record[4096];assert(rocell_diag::shoulder_event_json(event,pose,sid,result,
       "abababababababababababababababab","mixed-offline",sequence++,record,sizeof(record)));
     if(fault<2)std::cout<<record<<"\n";
     if(fault==5&&std::string(event)=="PRELOAD_INTENT")bus.position[2]+=1;
     if(fault==6&&std::string(event)=="PRELOAD_INTENT")return false;
     if(fault==7&&std::string(event)=="PRELOAD_RESULT")clock.tick+=2100000;
     return true;
   };
   bool ok=owner.run(bus,clock,evidence,admit);
   assert(ok==(fault<2));assert(bus.writes==((fault==5||fault==6)?0:1));
   const int reads=bus.reads,writes=bus.writes;
   assert(!owner.run(bus,clock,evidence,admit)&&bus.reads==reads&&bus.writes==writes);
   if(ok)assert(std::string(owner.reason())==(fault?"TARGET_OBSERVED_ENABLED":"TARGET_OBSERVED_PASSIVE"));
 }
 std::cout<<"MIXED_SHOULDER_NATIVE_PASSED\n";
}

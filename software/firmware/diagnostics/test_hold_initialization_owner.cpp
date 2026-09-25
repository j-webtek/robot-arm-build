#include <cassert>
#include <cstring>
#include "hold_initialization_owner.h"
struct Clock {uint64_t tick=100;uint64_t now_us(){return ++tick;}};
struct Bus {
  int End=0,Level=1,Error=0,reads=0,writes=0,enables=0,bad=-1;
  bool automatic=true,lost_ack=false,ignore_goal=false,ignore_enable=false;
  uint8_t elbow_moving=0;
  unsigned position[7]={2048,2390,1727,2723,2041,2042,2051};
  unsigned goal[7]={},torque[7]={};
  int Read(uint8_t id,uint8_t address,uint8_t* out,uint8_t width){
    assert(id>=11&&id<=17);const auto i=id-11;
    std::memset(out,0,width);Error=0;
    if(address==42){assert(width==2);out[0]=goal[i]&255;out[1]=goal[i]>>8;}
    else if(address==56){assert(width==15);out[0]=position[i]&255;out[1]=position[i]>>8;
      if(i==3)out[10]=elbow_moving;}
    else if(address==40){assert(width==1);out[0]=torque[i];}
    else assert(address==33&&width==1);
    return reads++==bad?0:width;
  }
  int WritePosEx(uint8_t id,int16_t target,uint16_t speed,uint8_t acc){
    assert(id==14&&target==2723&&speed==20&&acc==1);++writes;
    if(!ignore_goal)goal[3]=target;
    if(automatic)torque[3]=1;
    Error=0;return lost_ack?0:1;
  }
  int EnableTorque(uint8_t id,uint8_t enabled){
    assert(id==14&&enabled==1);++enables;
    if(!ignore_enable)torque[3]=1;
    Error=0;return lost_ack?0:1;
  }
};
using namespace rocell_diag;
HoldInitializationPolicy policy(bool enable=false){
  HoldInitializationPolicy p;p.permit_explicit_enable=enable;
  const unsigned pos[7]={2048,2390,1727,2723,2041,2042,2051};
  for(size_t i=0;i<7;++i){p.minimum[i]=pos[i]-8;p.maximum[i]=pos[i]+8;}
  return p;
}
void step(HoldInitializationOwner& owner,Bus& bus,Clock& clock){clock.tick+=110000;owner.poll(bus,clock);}
void run(HoldInitializationOwner& owner,Bus& bus,Clock& clock){
  for(int i=0;i<10;++i)step(owner,bus,clock);
}
int main(){
  // The first stationary check must follow the configured post-write dwell.
  // A busy flag inside the dwell is not permission for another write.
  for(int stays_busy=0;stays_busy<2;++stays_busy){
   Bus bus;bus.automatic=false;bus.torque[3]=1;bus.goal[3]=2723;Clock clock;
   HoldInitializationOwner owner(policy(true));
   step(owner,bus,clock);step(owner,bus,clock);step(owner,bus,clock);
   assert(bus.writes==1&&owner.phase()==HoldPhase::ReadHold);
   int reads=bus.reads;bus.elbow_moving=1;clock.tick+=15000;owner.poll(bus,clock);
   assert(bus.reads==reads&&bus.writes==1&&owner.phase()==HoldPhase::ReadHold);
   bus.elbow_moving=stays_busy;run(owner,bus,clock);
   assert(owner.phase()==(stays_busy?HoldPhase::Fault:HoldPhase::Captured));
   assert(bus.writes==1&&bus.enables==0);
  }
  {Bus bus;bus.automatic=false;bus.torque[3]=1;bus.goal[3]=2724;
   Clock clock;HoldInitializationOwner owner(policy(true));run(owner,bus,clock);
   assert(owner.phase()==HoldPhase::Captured&&bus.writes==1&&bus.enables==0);
   assert(bus.torque[3]==1&&bus.goal[3]==2723);}
  {Bus bus;bus.torque[3]=1;bus.goal[3]=2726;Clock clock;
   HoldInitializationOwner owner(policy(true));run(owner,bus,clock);
   assert(owner.phase()==HoldPhase::Fault&&bus.writes==0&&bus.enables==0);
   assert(std::strcmp(owner.reason(),"HOLD_ENABLED_ELBOW_NOT_TRACKING")==0);}
  {Bus bus;bus.automatic=false;bus.torque[3]=1;bus.goal[3]=2723;Clock clock;
   HoldInitializationOwner owner(policy(true));
   step(owner,bus,clock);step(owner,bus,clock);step(owner,bus,clock);
   assert(bus.writes==1);bus.torque[3]=0;run(owner,bus,clock);
   assert(owner.phase()==HoldPhase::Fault&&bus.enables==0);}
  for(int explicit_enable=0;explicit_enable<2;++explicit_enable){
    Bus bus;bus.automatic=!explicit_enable;Clock clock;HoldInitializationOwner owner(policy(explicit_enable));
    run(owner,bus,clock);
    assert(owner.phase()==HoldPhase::Captured);
    assert(bus.writes==1&&bus.enables==explicit_enable);
    assert(owner.scan_count()==(explicit_enable?7:5));
    assert(owner.action_count()==unsigned(1+explicit_enable));
    auto* a=owner.action(0);assert(a->address==41&&a->width==7);
    assert(a->bytes[1]==0xa3&&a->bytes[2]==0x0a&&a->bytes[5]==20);
    assert(a->ack.status==DispatchStatus::Succeeded&&a->finished_us>=a->started_us);
    assert(owner.scan(0)->joint(1)->position+owner.scan(0)->joint(2)->position==4117);
    int reads=bus.reads;run(owner,bus,clock);assert(bus.reads==reads);
  }
  {Bus bus;bus.lost_ack=true;Clock clock;HoldInitializationOwner owner(policy());run(owner,bus,clock);
   assert(owner.phase()==HoldPhase::Fault&&bus.writes==1&&bus.enables==0&&bus.torque[3]==1);
   assert(std::strcmp(owner.reason(),"HOLD_ACK_UNCERTAIN_OR_FAILED")==0);}
  {Bus bus;bus.automatic=false;Clock clock;HoldInitializationOwner owner(policy());run(owner,bus,clock);
   assert(owner.phase()==HoldPhase::Fault&&bus.writes==1&&bus.enables==0);}
  {Bus bus;bus.ignore_goal=true;Clock clock;HoldInitializationOwner owner(policy());run(owner,bus,clock);
   assert(owner.phase()==HoldPhase::Fault&&bus.writes==1);}
  {Bus bus;bus.automatic=false;bus.ignore_enable=true;Clock clock;HoldInitializationOwner owner(policy(true));
   run(owner,bus,clock);assert(owner.phase()==HoldPhase::Fault&&bus.enables==1);}
  for(int failed_read=0;failed_read<140;++failed_read){
    Bus bus;bus.bad=failed_read;Clock clock;HoldInitializationOwner owner(policy());run(owner,bus,clock);
    assert(owner.phase()==HoldPhase::Fault&&bus.writes<=1&&bus.enables==0);
    int reads=bus.reads;run(owner,bus,clock);assert(bus.reads==reads);
  }
  {Bus bus;bus.Level=0;Clock clock;HoldInitializationOwner owner(policy());run(owner,bus,clock);
   assert(owner.phase()==HoldPhase::Fault&&bus.reads==0&&bus.writes==0);}
  {Bus bus;Clock clock;HoldInitializationOwner owner(policy());step(owner,bus,clock);step(owner,bus,clock);
   bus.position[3]+=3;run(owner,bus,clock);assert(owner.phase()==HoldPhase::Fault&&bus.writes==0);}
  {Bus bus;Clock clock;HoldInitializationOwner owner(policy());step(owner,bus,clock);step(owner,bus,clock);
   bus.torque[1]=1;run(owner,bus,clock);assert(owner.phase()==HoldPhase::Fault&&bus.writes==0);}
  {Bus bus;Clock clock;HoldInitializationOwner owner(policy());step(owner,bus,clock);
   clock.tick+=600000;owner.poll(bus,clock);assert(owner.phase()==HoldPhase::Fault&&bus.writes==0);}
  {Bus bus;Clock clock;HoldInitializationOwner owner(policy());step(owner,bus,clock);step(owner,bus,clock);
   bus.Level=0;run(owner,bus,clock);assert(owner.phase()==HoldPhase::Fault&&bus.writes==0);}
  {Bus bus;Clock clock;auto p=policy();p.deadline_us=200000;HoldInitializationOwner owner(p);
   run(owner,bus,clock);assert(owner.phase()==HoldPhase::Fault&&bus.writes==0);}
  {Bus bus;Clock clock;HoldInitializationOwner owner(policy());step(owner,bus,clock);
   clock.tick=10;owner.poll(bus,clock);assert(owner.phase()==HoldPhase::Fault&&bus.writes==0);}
  {Bus bus;Clock clock;auto p=policy();p.speed=0;HoldInitializationOwner owner(p);
   run(owner,bus,clock);assert(owner.phase()==HoldPhase::Fault&&bus.reads==0);}
  return 0;
}

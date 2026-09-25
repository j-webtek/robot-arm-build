#include <cassert>
#include <cstring>
#include "held_elbow_leg_owner.h"
using namespace rocell_diag;
struct Clock{uint64_t tick=100;uint64_t now_us(){return ++tick;}};
struct Bus{
  int End=0,Level=1,Error=0,reads=0,writes=0,bad=-1;
  bool lost=false,ignore_goal=false,stuck=false,wrong=false;
  unsigned pos[7]={2047,2395,1722,2902,2035,2045,2047};
  unsigned goal[7]={0,0,0,2902,0,0,0},torque[7]={0,0,0,1,0,0,0};
  int Read(uint8_t id,uint8_t address,uint8_t* out,uint8_t width){
    auto i=id-11;assert(i<7);std::memset(out,0,width);Error=0;
    if(address==42){out[0]=goal[i]&255;out[1]=goal[i]>>8;}
    else if(address==56){out[0]=pos[i]&255;out[1]=pos[i]>>8;}
    else if(address==40)out[0]=torque[i];
    else assert(address==33);
    return reads++==bad?0:width;
  }
  int WritePosEx(uint8_t id,int16_t target,uint16_t speed,uint8_t acc){
    assert(id==14&&speed==20&&acc==1);++writes;
    if(!ignore_goal)goal[3]=target;
    if(!stuck)pos[3]=wrong?pos[3]-3:target;
    return lost?0:1;
  }
};
bool healthy(void* p){return !p||*static_cast<bool*>(p);}
HoldInitializationPolicy policy(){
  HoldInitializationPolicy p;Bus b;
  for(int i=0;i<7;++i){p.minimum[i]=b.pos[i]-16;p.maximum[i]=b.pos[i]+16;}
  return p;
}
void step(HeldElbowLegOwner& o,Bus& b,Clock& c){c.tick+=110000;o.poll(b,c);}
void run(HeldElbowLegOwner& o,Bus& b,Clock& c){for(int i=0;i<30;++i)step(o,b,c);}
int main(){
  {Bus b;Clock c;HeldElbowLegOwner f(policy(),2908,2,healthy);run(f,b,c);
   assert(f.phase()==HeldLegPhase::Arrived&&b.writes==1&&f.scan_count()==5);
   assert(f.action()->bytes[1]==(2908&255)&&f.action()->bytes[2]==(2908>>8));
   HeldElbowLegOwner r(policy(),2902,2,healthy);
   assert(r.bind_start(*f.scan(f.scan_count()-1)));run(r,b,c);
   assert(r.phase()==HeldLegPhase::Arrived&&b.writes==2&&r.anchor()==2908);}
  // Changes during export/authorization must not become the return baseline.
  for(int change=0;change<5;++change){Bus b;Clock c;
   HeldElbowLegOwner f(policy(),2908,2,healthy);run(f,b,c);
   HeldElbowLegOwner r(policy(),2902,2,healthy);
   assert(r.bind_start(*f.scan(f.scan_count()-1)));
   if(change==0)b.pos[1]+=3;
   if(change==1)b.goal[1]=1;
   if(change==2)b.torque[1]=1;
   if(change==3){b.pos[3]+=3;b.goal[3]+=3;}
   if(change==4)b.goal[3]-=1;
   run(r,b,c);assert(r.phase()==HeldLegPhase::Fault&&b.writes==1);
   assert(!strcmp(r.reason(),"LEG_BOUND_START_CHANGED"));
   const int reads=b.reads;run(r,b,c);assert(b.reads==reads&&b.writes==1);}
  {Bus b;Clock c;HeldElbowLegOwner f(policy(),2908,2,healthy);run(f,b,c);
   HeldElbowLegOwner r(policy(),2902,2,healthy);
   assert(r.bind_start(*f.scan(f.scan_count()-1)));
   assert(!r.bind_start(*f.scan(f.scan_count()-1)));run(r,b,c);assert(b.writes==1);}
  {Bus b;Clock c;HoldStateSnapshot incomplete;
   HeldElbowLegOwner r(policy(),2902,2,healthy);assert(!r.bind_start(incomplete));
   run(r,b,c);assert(b.reads==0&&b.writes==0);}
  {Bus b;b.stuck=true;Clock c;HeldElbowLegOwner o(policy(),2908,2,healthy);run(o,b,c);
   assert(o.phase()==HeldLegPhase::NotArrived&&b.writes==1);}
  for(int fault=0;fault<4;++fault){Bus b;Clock c;
   b.lost=fault==0;b.ignore_goal=fault==1;b.wrong=fault==2;if(fault==3)b.torque[3]=0;
   HeldElbowLegOwner o(policy(),2908,2,healthy);run(o,b,c);
   assert(o.phase()==HeldLegPhase::Fault&&b.writes==(fault==3?0:1));}
  for(int bad=0;bad<140;++bad){Bus b;b.bad=bad;Clock c;
   HeldElbowLegOwner o(policy(),2908,2,healthy);run(o,b,c);
   assert(o.phase()==HeldLegPhase::Fault&&b.writes<=1);
   int reads=b.reads,writes=b.writes;run(o,b,c);assert(b.reads==reads&&b.writes==writes);}
  {Bus b;Clock c;HeldElbowLegOwner o(policy(),2908,2,healthy);step(o,b,c);step(o,b,c);
   b.pos[1]+=3;run(o,b,c);assert(o.phase()==HeldLegPhase::Fault&&b.writes==0);}
  {Bus b;Clock c;HeldElbowLegOwner o(policy(),2908,2,healthy);step(o,b,c);step(o,b,c);step(o,b,c);
   o.export_failed();run(o,b,c);assert(o.phase()==HeldLegPhase::Fault&&b.writes==1);}
  {Bus b;Clock c;bool allowed=true;HeldElbowLegOwner o(policy(),2908,2,healthy,&allowed);
   step(o,b,c);allowed=false;run(o,b,c);assert(o.phase()==HeldLegPhase::Fault&&b.writes==0);}
  {Bus b;Clock c;HeldElbowLegOwner o(policy(),2908,2,nullptr);run(o,b,c);assert(b.reads==0&&b.writes==0);}
  {Bus b;Clock c;HeldElbowLegOwner o(policy(),2908,2,healthy);step(o,b,c);c.tick+=600000;
   run(o,b,c);assert(o.phase()==HeldLegPhase::Fault&&b.writes==0);}
  return 0;
}

#include <cassert>
#include <cstring>
#include "whole_arm_baseline.h"
#include "whole_arm_baseline_json.h"
struct Clock {uint64_t tick=1000,step=1;uint64_t now_us(){return tick+=step;}};
struct Bus {
  int End=0,Error=0,reads=0,bad_id=0,mode=0;
  int Read(uint8_t id,uint8_t address,uint8_t* bytes,uint8_t width) {
    assert(id==11+reads/2 && (address==42||address==56));++reads;
    unsigned count=2000;
    if(id==bad_id && mode==1)return 0;
    if(id==bad_id && mode==2 && width==15)bytes[10]=1;
    if(id==bad_id && mode==3)count=2200;
    if(id==bad_id && mode==4 && width==15)count=2005;
    if(id==bad_id && mode==5)Error=1;
    bytes[0]=count&255;bytes[1]=count>>8;return width;
  }
};
rocell_diag::WholeArmBaselinePolicy policy() {
  rocell_diag::WholeArmBaselinePolicy result={};
  for(auto& joint:result.joints)joint={1990,2010};
  result.tracking_tolerance=2;result.maximum_pair_us=100;
  result.maximum_scan_us=1000;result.maximum_age_us=1000;return result;
}
int main(){
  {Bus bus;Clock clock;rocell_diag::WholeArmBaseline gate(policy());
   assert(gate.check(bus,clock)&&bus.reads==14&&gate.count()==7);
   for(size_t i=0;i<7;++i){assert(gate.pair(i)->target.servo_id==11+i);assert(gate.pair(i)->target.sequence==i*2);}
   assert(!gate.pair(7));assert(gate.fresh(clock.now_us()));
   char output[2048];assert(rocell_diag::whole_arm_baseline_json(gate,"boot","command",output,sizeof(output)));puts(output);
   char small[8]={'x'};assert(!rocell_diag::whole_arm_baseline_json(gate,"boot","command",small,sizeof(small))&&!small[0]);
   assert(!gate.fresh(1000));assert(!gate.fresh(3000));
   assert(!gate.fresh(clock.now_us())); // A clock fault cannot revive the gate.
   assert(!gate.check(bus,clock)&&bus.reads==14);}
  for(int id=11;id<=17;++id)for(int mode=1;mode<=5;++mode){
    Bus bus;Clock clock;bus.bad_id=id;bus.mode=mode;
    rocell_diag::WholeArmBaseline gate(policy());assert(!gate.check(bus,clock));
    assert(bus.reads==(id-10)*2 && gate.count()==static_cast<size_t>(id-10));
    assert(!gate.fresh(clock.now_us()));int before=bus.reads;
    assert(!gate.check(bus,clock)&&bus.reads==before);
    if(mode==1 || mode==5)assert(gate.pair(id-11)->feedback.status==rocell_diag::ReadStatus::Failed);
    if(id==14 && mode==1){char out[2048];assert(rocell_diag::whole_arm_baseline_json(gate,"boot","command",out,sizeof(out)));puts(out);}
  }
  for(int kind=0;kind<5;++kind){
    Bus bus;Clock clock;auto limits=policy();
    if(kind==0)limits.joints[2]={2100,2000};
    if(kind==1)limits.joints[2]={2000,5000};
    if(kind==2)limits.maximum_pair_us=0;
    if(kind==3)limits.tracking_tolerance=17;
    if(kind==4)bus.End=1;
    rocell_diag::WholeArmBaseline gate(limits);assert(!gate.check(bus,clock)&&bus.reads==0);
  }
  {Bus bus;Clock clock;auto limits=policy();limits.maximum_age_us=10;
   rocell_diag::WholeArmBaseline gate(limits);assert(!gate.check(bus,clock));
   assert(strcmp(gate.reason(),"WHOLE_ARM_STALE")==0 && bus.reads<14);}
  {Bus bus;Clock clock;clock.step=50;
   rocell_diag::WholeArmBaseline gate(policy());assert(!gate.check(bus,clock)&&bus.reads==2);
   assert(strcmp(gate.reason(),"WHOLE_ARM_TIMING_INVALID")==0);}
  {Bus bus;Clock clock;clock.tick=INT64_MAX-1000;auto limits=policy();
   limits.maximum_pair_us=1000000;limits.maximum_scan_us=7000000;limits.maximum_age_us=1000000;
   rocell_diag::WholeArmBaseline gate(limits);assert(gate.check(bus,clock));
   char identity[129];memset(identity,'a',128);identity[128]=0;
   char out[2048];assert(rocell_diag::whole_arm_baseline_json(gate,identity,identity,out,sizeof(out)));puts(out);}
}

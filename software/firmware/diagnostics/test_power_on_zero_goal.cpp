// Regression derived from powered-baseline-20260918-01. No hardware access.
#include <cassert>
#include <cstring>
#include "whole_arm_baseline.h"
#include "fresh_elbow_baseline.h"
struct Clock {uint64_t tick=100;uint64_t now_us(){return ++tick;}};
struct Bus {
  int End=0,Error=0,reads=0;
  int Read(uint8_t id,uint8_t address,uint8_t* bytes,uint8_t width){
    static const unsigned positions[]={2047,2390,1727,2723,2041,2042,2051};
    ++reads;assert(id>=11&&id<=17);
    if(address==56){bytes[0]=positions[id-11]&255;bytes[1]=positions[id-11]>>8;}
    else assert(address==42); // Zero goals despite valid stationary positions.
    return width;
  }
};
int main(){
  using namespace rocell_diag;
  {Bus bus;Clock clock;WholeArmBaselinePolicy policy={};
   const unsigned positions[]={2047,2390,1727,2723,2041,2042,2051};
   for(size_t i=0;i<7;++i)policy.joints[i]={static_cast<uint16_t>(positions[i]-16),static_cast<uint16_t>(positions[i]+16)};
   policy.tracking_tolerance=2;policy.maximum_pair_us=1000000;
   policy.maximum_scan_us=7000000;policy.maximum_age_us=1000000;
   WholeArmBaseline gate(policy);
   assert(!gate.check(bus,clock));
   assert(!strcmp(gate.reason(),"WHOLE_ARM_OUTSIDE_WINDOW"));
   assert(bus.reads==2);}
  {Bus bus;Clock clock;FreshElbowBaseline gate;
   assert(!gate.check(bus,clock,2723,16,2,1000000,1000000));
   assert(!strcmp(gate.reason(),"BASELINE_OUTSIDE_PROFILE"));
   assert(bus.reads==2);}
}

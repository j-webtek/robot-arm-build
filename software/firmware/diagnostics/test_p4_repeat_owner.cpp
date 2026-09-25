#include "p4_repeat_owner.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
using namespace rocell_diag;
struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
int main(int argc,char** argv){
  const std::string mode=argc>1?argv[1]:"success";
  const unsigned bad_leg=argc>2?unsigned(std::atoi(argv[2])):1;
  P4RepeatOwner owner;Clock clock;unsigned transmissions=0;
  uint16_t pos[7]={2047,2225,1890,2716,1977,2041,2047};
  uint16_t goals[7]={2047,2217,1897,2711,1980,2040,2047};
  auto reserve=[](){return true;};auto admitted=[](){return true;};
  if(!owner.begin(reserve,clock))return 1;
  for(unsigned leg=1;leg<=12;++leg){
    unsigned acquisitions=0;
    auto acquire=[&](ShoulderPreloadPose& s){
      s={};s.started_us=clock.now-50000;s.finished_us=clock.now;
      if(mode=="drift"&&leg==bad_leg&&acquisitions>=4)pos[0]=2050;
      if(mode=="source"&&leg==bad_leg&&acquisitions==0)goals[4]++;
      if(mode=="prewrite"&&leg==bad_leg&&acquisitions==3)pos[4]+=2;
      for(int i=0;i<7;++i){s.position[i]=pos[i];s.goal[i]=goals[i];s.torque[i]=1;
        s.feedback[i][0]=uint8_t(pos[i]);s.feedback[i][1]=uint8_t(pos[i]>>8);}
      ++acquisitions;return true;
    };
    auto write=[&](uint8_t id,uint16_t target,uint16_t speed,uint8_t acc){
      ++transmissions;
      if(id!=15||target!=P4RepeatPolicy::targets[leg-1]||speed!=20||acc!=1)return false;
      if(mode=="delivery"&&leg==bad_leg)return false;
      goals[4]=target;pos[4]=target-3;return true;
    };
    auto evidence=[&](const char* event,const ShoulderPreloadPose&){
      return !(mode=="evidence"&&leg==bad_leg&&std::strcmp(event,"P4_REPEAT_LEG_INTENT")==0);
    };
    for(unsigned i=0;i<7&&owner.state()!=P4RepeatOwner::State::Fault;++i){
      if(mode=="timeout"&&leg==bad_leg&&i==0)clock.now+=10000001;
      clock.now+=150000;owner.poll(acquire,write,clock,evidence,admitted);
    }
    if((mode=="delivery"||mode=="drift"||mode=="evidence"||mode=="source"||mode=="prewrite"||mode=="timeout")&&leg==bad_leg){
      return owner.state()==P4RepeatOwner::State::Fault&&
        transmissions==leg-((mode=="delivery"||mode=="drift")?0:1)&&!owner.begin(reserve,clock)?0:2;
    }
    if(owner.state()!=P4RepeatOwner::State::AwaitExport)return 3;
    uint8_t boot[16],raw[1130],digest[32];for(auto& x:boot)x=0xab;
    // Deterministic mock digest callback; production route must provide SHA-256.
    auto hash=[&](const uint8_t*,size_t n,uint8_t* out){
      if(n!=1130)return false;for(unsigned i=0;i<32;++i)out[i]=digest[i]=uint8_t(i+leg);return true;};
    if(owner.seal_record(boot,raw,sizeof(raw),hash)!=1130)return 4;
    if(mode=="success"){for(auto b:raw)std::printf("%02x",b);std::puts("");}
    auto wrong=digest[0];digest[0]^=1;
    if(owner.acknowledge(leg,digest,clock))return 5;
    digest[0]=wrong;
    if(owner.acknowledge(leg+1,digest,clock))return 6;
    owner.poll(acquire,write,clock,evidence,admitted);
    if(transmissions!=leg)return 7;
    if(mode=="expired"&&leg==bad_leg){
      clock.now+=30000001;
      return !owner.acknowledge(leg,digest,clock)&&owner.state()==P4RepeatOwner::State::Fault?0:8;
    }
    if(!owner.acknowledge(leg,digest,clock)||owner.acknowledge(leg,digest,clock))return 9;
    owner.poll(acquire,write,clock,evidence,admitted);
    if(transmissions!=leg)return 11;
    if(leg<12){
      if(owner.begin_next(leg,clock)||!owner.begin_next(leg+1,clock)||owner.begin_next(leg+1,clock))return 12;
    }
  }
  return owner.state()==P4RepeatOwner::State::Complete&&owner.total_writes()==12&&
    transmissions==12&&!owner.begin(reserve,clock)?0:10;
}

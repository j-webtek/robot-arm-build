#include "air_typing_owner.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
using namespace rocell_diag;
struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
int main(int argc,char** argv){
  const std::string mode=argc>1?argv[1]:"success";
  const unsigned bad_leg=argc>2?unsigned(std::atoi(argv[2])):1;
  AirTypingOwner owner;Clock clock;unsigned transmissions=0;
  uint16_t pos[7]={2047,2225,1890,2716,1979,2041,2047};
  uint16_t goals[7]={2047,2217,1897,2711,1980,2040,2047};
  const int residual[7]={0,8,-7,5,-1,1,0};
  auto reserve=[](){return true;};auto admitted=[](){return true;};
  if(!owner.begin(reserve,clock))return 1;
  for(unsigned leg=1;leg<=AirTypingPolicy::legs;++leg){
    unsigned acquisitions=0;
    auto acquire=[&](ShoulderPreloadPose& s){
      s={};s.started_us=clock.now-50000;s.finished_us=clock.now;
      if(mode=="source"&&leg==bad_leg&&acquisitions==0)goals[4]++;
      if(mode=="prewrite"&&leg==bad_leg&&acquisitions==3)pos[4]+=2;
      if(mode=="stale"&&leg==bad_leg&&acquisitions==0){
        s.started_us=clock.now-250000;s.finished_us=clock.now-200000;
      }
      for(int i=0;i<7;++i){s.position[i]=pos[i];s.goal[i]=goals[i];s.torque[i]=1;
        s.feedback[i][0]=uint8_t(pos[i]);s.feedback[i][1]=uint8_t(pos[i]>>8);}
      ++acquisitions;return true;
    };
    auto write=[&](const uint16_t (&target)[7],uint16_t speed,uint8_t acc){
      ++transmissions;
      if(speed!=20||acc!=1)return false;
      for(int i=0;i<7;++i)if(target[i]!=AirTypingPolicy::targets[leg-1][i])return false;
      if(mode=="delivery"&&leg==bad_leg)return false;
      for(int i=0;i<7;++i){goals[i]=target[i];pos[i]=uint16_t(int(target[i])+residual[i]);}
      if(mode=="wrong_endpoint"&&leg==bad_leg)pos[4]=uint16_t(target[4]+30);
      return true;
    };
    auto evidence=[&](const char* event,const ShoulderPreloadPose&){
      return !(mode=="evidence"&&leg==bad_leg&&
               std::strcmp(event,"AIR_TYPING_LEG_INTENT")==0);
    };
    for(unsigned i=0;i<80&&owner.state()!=AirTypingOwner::State::Fault&&
                      owner.state()!=AirTypingOwner::State::AwaitExport;++i){
      if(mode=="timeout"&&leg==bad_leg&&i==0)clock.now+=10000001;
      clock.now+=150000;owner.poll(acquire,write,clock,evidence,admitted);
    }
    if((mode=="delivery"||mode=="wrong_endpoint"||mode=="evidence"||
        mode=="source"||mode=="prewrite"||mode=="stale"||mode=="timeout")&&leg==bad_leg){
      return owner.state()==AirTypingOwner::State::Fault&&
             !owner.begin(reserve,clock)?0:2;
    }
    if(owner.state()!=AirTypingOwner::State::AwaitExport)return 3;
    uint8_t boot[16],raw[1130],digest[32];for(auto& x:boot)x=0xab;
    auto hash=[&](const uint8_t*,size_t n,uint8_t* out){
      if(n!=1130)return false;
      for(unsigned i=0;i<32;++i)out[i]=digest[i]=uint8_t(i+leg);
      return true;};
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
      return !owner.acknowledge(leg,digest,clock)&&
             owner.state()==AirTypingOwner::State::Fault?0:8;
    }
    if(!owner.acknowledge(leg,digest,clock)||owner.acknowledge(leg,digest,clock))return 9;
    owner.poll(acquire,write,clock,evidence,admitted);
    if(transmissions!=leg)return 10;
    if(leg<AirTypingPolicy::legs){
      if(owner.begin_next(leg,clock)||!owner.begin_next(leg+1,clock)||
         owner.begin_next(leg+1,clock))return 11;
    }
  }
  return owner.state()==AirTypingOwner::State::Complete&&
         owner.total_writes()==AirTypingPolicy::legs&&
         transmissions==AirTypingPolicy::legs&&!owner.begin(reserve,clock)?0:12;
}

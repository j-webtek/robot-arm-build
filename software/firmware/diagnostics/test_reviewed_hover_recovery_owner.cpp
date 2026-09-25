#include "reviewed_hover_recovery_policy.h"
#include "reviewed_hover_owner.h"
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <string>
using namespace rocell_diag;
struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};

int main(int argc,char** argv){
  const std::string mode=argc>1?argv[1]:"success";
  const unsigned bad_leg=argc>2?unsigned(std::atoi(argv[2])):1;
  constexpr uint8_t ids[5]={0,1,2,1,0};
  ReviewedHoverOwnerT<ReviewedHoverRecoveryPolicy> owner;
  Clock clock;unsigned transmissions=0;
  uint8_t boot[16],manifest_digest[32];
  for(auto& byte:boot)byte=0xab;
  for(unsigned i=0;i<32;++i)manifest_digest[i]=uint8_t(i+1);
  if(!owner.configure(ids,5,boot,manifest_digest)||
     owner.configure(ids,5,boot,manifest_digest))return 1;
  uint16_t pos[7]={2041,2094,2020,2620,2199,2041,2047};
  uint16_t goals[7]={2047,2093,2021,2618,2197,2040,2047};
  const int residual[7]={-6,1,-1,2,2,1,0};
  auto reserve=[](){return true;};auto admitted=[](){return true;};
  if(!owner.begin(reserve,clock))return 2;
  for(unsigned leg=1;leg<=5;++leg){
    unsigned acquisitions=0;
    auto acquire=[&](ShoulderPreloadPose& sample){
      sample={};sample.started_us=clock.now-50000;sample.finished_us=clock.now;
      if(mode=="source"&&leg==bad_leg&&acquisitions==0)goals[4]++;
      if(mode=="prewrite"&&leg==bad_leg&&acquisitions==3)pos[4]+=2;
      if(mode=="stale"&&leg==bad_leg&&acquisitions==0){
        sample.started_us=clock.now-250000;sample.finished_us=clock.now-200000;
      }
      for(unsigned i=0;i<7;++i){
        sample.position[i]=pos[i];sample.goal[i]=goals[i];sample.torque[i]=1;
        sample.feedback[i][0]=uint8_t(pos[i]);
        sample.feedback[i][1]=uint8_t(pos[i]>>8);
      }
      ++acquisitions;return true;
    };
    auto write=[&](const uint16_t (&target)[7],uint16_t speed,uint8_t acc){
      ++transmissions;
      if(speed!=20||acc!=1)return false;
      for(unsigned i=0;i<7;++i)
        if(target[i]!=ReviewedHoverManifest::goals[ids[leg-1]][i])return false;
      if(mode=="delivery"&&leg==bad_leg)return false;
      for(unsigned i=0;i<7;++i){
        if(goals[i]!=target[i])pos[i]=uint16_t(int(target[i])+residual[i]);
        goals[i]=target[i];
      }
      if(mode=="wrong_endpoint"&&leg==bad_leg)pos[4]=uint16_t(target[4]+30);
      return true;
    };
    auto evidence=[&](const char* event,const ShoulderPreloadPose&){
      return !(mode=="evidence"&&leg==bad_leg&&
               std::strcmp(event,"REVIEWED_HOVER_LEG_INTENT")==0);
    };
    for(unsigned n=0;n<80&&owner.state()!=decltype(owner)::State::Fault&&
          owner.state()!=decltype(owner)::State::AwaitExport;++n){
      if(mode=="timeout"&&leg==bad_leg&&n==0)clock.now+=10000001;
      clock.now+=150000;owner.poll(acquire,write,clock,evidence,admitted);
    }
    if((mode=="source"||mode=="prewrite"||mode=="stale"||mode=="delivery"||
        mode=="wrong_endpoint"||mode=="evidence"||mode=="timeout")&&leg==bad_leg){
      const unsigned expected=(mode=="delivery"||mode=="wrong_endpoint")?leg:leg-1;
      return owner.state()==decltype(owner)::State::Fault&&
             !owner.begin(reserve,clock)&&transmissions==expected?0:3;
    }
    if(owner.state()!=decltype(owner)::State::AwaitExport)return 4;
    uint8_t raw[1163],digest[32];
    auto hash=[&](const uint8_t*,size_t size,uint8_t* out){
      if(size!=1163||mode=="hash"&&leg==bad_leg)return false;
      for(unsigned i=0;i<32;++i)out[i]=digest[i]=uint8_t(i+leg);
      return true;
    };
    if(mode=="hash"&&leg==bad_leg)
      return owner.seal_record(raw,sizeof(raw),hash)==0&&
             owner.state()==decltype(owner)::State::Fault&&transmissions==leg?0:5;
    if(owner.seal_record(raw,sizeof(raw),hash)!=1163||raw[58]!=leg||
       raw[59]!=ids[leg-1])return 6;
    if(mode=="records"){
      for(uint8_t byte:raw)std::printf("%02x",unsigned(byte));
      std::printf("\n");
    }
    owner.poll(acquire,write,clock,evidence,admitted);
    if(transmissions!=leg)return 7;
    if(mode=="expired"&&leg==bad_leg){
      clock.now+=30000001;
      return !owner.acknowledge(leg,digest,clock)&&
             owner.state()==decltype(owner)::State::Fault&&transmissions==leg?0:8;
    }
    if(!owner.acknowledge(leg,digest,clock)||
       owner.acknowledge(leg,digest,clock))return 9;
    if(leg<5){
      if(owner.begin_next(leg,clock)||!owner.begin_next(leg+1,clock)||
         owner.begin_next(leg+1,clock))return 10;
    }
  }
  return owner.state()==decltype(owner)::State::Complete&&
         owner.total_writes()==5&&transmissions==5?0:11;
}

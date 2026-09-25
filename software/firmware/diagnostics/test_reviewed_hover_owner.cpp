#include "reviewed_hover_owner.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
using namespace rocell_diag;
struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
int main(int argc,char** argv){
  const std::string mode=argc>1?argv[1]:"success";
  const unsigned bad_leg=argc>2?unsigned(std::atoi(argv[2])):1;
  constexpr uint8_t ids[16]={1,2,1,0,4,5,4,3,1,2,1,0,4,5,4,3};
  ReviewedHoverOwner owner;Clock clock;unsigned transmissions=0;
  uint8_t boot[16],manifest_digest[32];
  for(auto& x:boot)x=0xab;
  for(unsigned i=0;i<32;++i)manifest_digest[i]=uint8_t(i+1);
  if(!owner.configure(ids,16,boot,manifest_digest)||
     owner.configure(ids,16,boot,manifest_digest))return 1;
  uint16_t pos[7]={2040,2082,2033,2609,2233,2041,2047};
  uint16_t goals[7]={2047,2075,2039,2600,2233,2040,2047};
  const int residual[7]={0,1,-1,1,2,1,0};
  auto reserve=[](){return true;};auto admitted=[](){return true;};
  if(!owner.begin(reserve,clock))return 2;
  for(unsigned leg=1;leg<=16;++leg){
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
      for(int i=0;i<7;++i)if(target[i]!=ReviewedHoverManifest::goals[ids[leg-1]][i])return false;
      if(mode=="delivery"&&leg==bad_leg)return false;
      for(int i=0;i<7;++i){
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
    for(unsigned i=0;i<80&&owner.state()!=ReviewedHoverOwner::State::Fault&&
                      owner.state()!=ReviewedHoverOwner::State::AwaitExport;++i){
      if(mode=="timeout"&&leg==bad_leg&&i==0)clock.now+=10000001;
      clock.now+=150000;owner.poll(acquire,write,clock,evidence,admitted);
    }
    if((mode=="delivery"||mode=="wrong_endpoint"||mode=="evidence"||
        mode=="source"||mode=="prewrite"||mode=="stale"||mode=="timeout")&&leg==bad_leg){
      const unsigned expected=(mode=="delivery"||mode=="wrong_endpoint")?leg:leg-1;
      return owner.state()==ReviewedHoverOwner::State::Fault&&
             !owner.begin(reserve,clock)&&transmissions==expected?0:3;
    }
    if(owner.state()!=ReviewedHoverOwner::State::AwaitExport)return 4;
    uint8_t raw[1163],digest[32];
    auto hash=[&](const uint8_t*,size_t n,uint8_t* out){
      if(n!=1163||mode=="hash"&&leg==bad_leg)return false;
      for(unsigned i=0;i<32;++i)out[i]=digest[i]=uint8_t(i+leg);
      return true;};
    if(mode=="hash"&&leg==bad_leg){
      return owner.seal_record(raw,sizeof(raw),hash)==0&&
             owner.state()==ReviewedHoverOwner::State::Fault&&
             transmissions==leg?0:5;
    }
    if(owner.seal_record(raw,sizeof(raw),hash)!=1163)return 6;
    if(std::memcmp(raw,"RCHOVERR01",10)||std::memcmp(raw+10,boot,16)||
       std::memcmp(raw+26,manifest_digest,32)||raw[58]!=leg||raw[59]!=ids[leg-1])return 7;
    if(mode=="success"){for(auto b:raw)std::printf("%02x",b);std::puts("");}
    auto wrong=digest[0];digest[0]^=1;
    if(owner.acknowledge(leg,digest,clock))return 8;
    digest[0]=wrong;
    if(owner.acknowledge(leg+1,digest,clock))return 9;
    owner.poll(acquire,write,clock,evidence,admitted);
    if(transmissions!=leg)return 10;
    if(mode=="expired"&&leg==bad_leg){
      clock.now+=30000001;
      return !owner.acknowledge(leg,digest,clock)&&
             owner.state()==ReviewedHoverOwner::State::Fault&&
             transmissions==leg?0:11;
    }
    if(!owner.acknowledge(leg,digest,clock)||owner.acknowledge(leg,digest,clock))return 12;
    owner.poll(acquire,write,clock,evidence,admitted);
    if(transmissions!=leg)return 13;
    if(leg<16){
      if(owner.begin_next(leg,clock)||!owner.begin_next(leg+1,clock)||
         owner.begin_next(leg+1,clock))return 14;
    }
  }
  return owner.state()==ReviewedHoverOwner::State::Complete&&
         owner.total_writes()==16&&transmissions==16&&
         !owner.begin(reserve,clock)?0:15;
}

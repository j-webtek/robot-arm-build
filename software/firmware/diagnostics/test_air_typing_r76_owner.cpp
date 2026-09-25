#include <air_typing_owner.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
using namespace rocell_diag;
struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
int main(int argc,char** argv){
  const std::string mode=argc>1?argv[1]:"success";
  AirTypingOwner owner;Clock clock;unsigned transmissions=0,acquisitions=0;
  uint16_t pos[7]={1949,2082,2033,2600,2235,2041,2047};
  uint16_t goals[7]={1941,2080,2034,2591,2236,2040,2047};
  const int residual[7]={8,2,-1,9,-1,1,0};
  auto reserve=[](){return true;};auto admitted=[](){return true;};
  if(!owner.begin(reserve,clock))return 1;
  auto acquire=[&](ShoulderPreloadPose& s){
    s={};s.started_us=clock.now-50000;s.finished_us=clock.now;
    if(mode=="source"&&acquisitions==0)goals[4]++;
    if(mode=="prewrite"&&acquisitions==3)pos[4]+=2;
    if(mode=="stale"&&acquisitions==0){s.started_us=clock.now-250000;s.finished_us=clock.now-200000;}
    for(int i=0;i<7;++i){s.position[i]=pos[i];s.goal[i]=goals[i];s.torque[i]=1;
      s.feedback[i][0]=uint8_t(pos[i]);s.feedback[i][1]=uint8_t(pos[i]>>8);}
    ++acquisitions;return true;
  };
  auto write=[&](const uint16_t (&target)[7],uint16_t speed,uint8_t acc){
    ++transmissions;
    if(speed!=20||acc!=1)return false;
    for(int i=0;i<7;++i)if(target[i]!=AirTypingPolicy::targets[0][i])return false;
    if(mode=="delivery")return false;
    for(int i=0;i<7;++i){goals[i]=target[i];pos[i]=uint16_t(int(target[i])+residual[i]);}
    if(mode=="wrong_endpoint")pos[4]=uint16_t(target[4]+30);
    if(mode=="passive_drift")pos[0]+=3;
    return true;
  };
  auto evidence=[&](const char* event,const ShoulderPreloadPose&){
    return !(mode=="evidence"&&std::strcmp(event,"AIR_TYPING_LEG_INTENT")==0);
  };
  for(unsigned i=0;i<80&&owner.state()!=AirTypingOwner::State::Fault&&
                    owner.state()!=AirTypingOwner::State::AwaitExport;++i){
    if(mode=="timeout"&&i==0)clock.now+=10000001;
    clock.now+=150000;owner.poll(acquire,write,clock,evidence,admitted);
  }
  if(mode!="success")return owner.state()==AirTypingOwner::State::Fault&&
                            !owner.begin(reserve,clock)?0:2;
  if(owner.state()!=AirTypingOwner::State::AwaitExport||transmissions!=1)return 3;
  uint8_t boot[16],raw[1130],digest[32];for(auto& x:boot)x=0xab;
  auto hash=[&](const uint8_t*,size_t n,uint8_t* out){
    if(n!=1130)return false;
    for(unsigned i=0;i<32;++i)out[i]=digest[i]=uint8_t(i+1);
    return true;};
  if(owner.seal_record(boot,raw,sizeof(raw),hash)!=1130)return 4;
  for(auto b:raw)std::printf("%02x",b);std::puts("");
  if(!owner.acknowledge(1,digest,clock)||owner.state()!=AirTypingOwner::State::Complete||
     owner.total_writes()!=1||owner.begin(reserve,clock))return 5;
  return 0;
}

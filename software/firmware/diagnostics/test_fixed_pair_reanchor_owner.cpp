#include "fixed_pair_reanchor_owner.h"
#include <cstdio>
#include <cstring>
#include <string>
using namespace rocell_diag;

struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
static ShoulderPreloadPose pose(unsigned index){
  ShoulderPreloadPose p;
  const bool after=index>=4;
  p.started_us=(after?2000000:1000000)+uint64_t(after?index-4:index)*150000;
  p.finished_us=p.started_us+50000;
  for(int i=0;i<7;++i){p.goal[i]=2000;p.position[i]=2000;p.torque[i]=1;}
  p.goal[1]=after?2389:2386;p.goal[2]=after?1725:1728;
  p.position[1]=after?2391:2390;p.position[2]=after?1724:1725;
  for(int i=0;i<7;++i){
    p.feedback[i][0]=uint8_t(p.position[i]);
    p.feedback[i][1]=uint8_t(p.position[i]>>8);
  }
  return p;
}
int main(int argc,char** argv){
  if(argc!=2)return 2;
  const std::string mode=argv[1];
  FixedPairReanchorOwner owner;Clock clock;
  auto reserve=[](){return true;};
  if(!owner.begin(reserve,clock))return 3;
  unsigned acquisition=0,transmissions=0;
  auto acquire=[&](ShoulderPreloadPose& out){
    if(acquisition>=7)return false;
    out=pose(acquisition);
    if(mode=="start_mismatch"&&acquisition==2)out.goal[1]=2385;
    if(mode=="prewrite_changed"&&acquisition==3)out.goal[1]=2385;
    if(mode=="endpoint_wrong"&&acquisition==6)out.goal[1]=2388;
    ++acquisition;return true;
  };
  auto write=[&](uint8_t a,uint8_t b,uint16_t x,uint16_t y,uint16_t speed,uint8_t acc){
    if(a!=12||b!=13||x!=2389||y!=1725||speed!=20||acc!=1)return false;
    ++transmissions;return mode!="write_uncertain";
  };
  auto evidence=[&](const char* event,const ShoulderPreloadPose&){
    return !(mode=="evidence_failure"&&std::strcmp(event,"FIXED_INTENT")==0);
  };
  auto admitted=[](){return true;};
  for(unsigned i=0;i<7&&owner.state()!=FixedPairReanchorOwner::State::Fault&&
                       owner.state()!=FixedPairReanchorOwner::State::AwaitExport;++i){
    clock.now=pose(i).finished_us+1000;
    owner.poll(acquire,write,clock,evidence,admitted);
  }
  if(mode=="success"){
    uint8_t boot[16],record[1127];for(auto& value:boot)value=0xab;
    const size_t size=owner.copy_result(boot,record,sizeof(record));
    if(size!=sizeof(record)){
      std::fprintf(stderr,"result size=%zu state=%d writes=%u reason=%s\n",size,
          int(owner.state()),owner.writes(),owner.reason());return 1;
    }
    for(size_t i=0;i<size;++i)std::printf("%02x",record[i]);
    std::printf("\n");
    if(owner.state()!=FixedPairReanchorOwner::State::AwaitExport||owner.writes()!=1||
       transmissions!=1||owner.mark_export_verified(false)||
       !owner.mark_export_verified(true)||
       owner.state()!=FixedPairReanchorOwner::State::Complete||owner.begin(reserve,clock))return 1;
    owner.poll(acquire,write,clock,evidence,admitted);
    return transmissions==1?0:1;
  }
  const unsigned expected_writes=(mode=="write_uncertain"||mode=="endpoint_wrong")?1:0;
  if(owner.state()!=FixedPairReanchorOwner::State::Fault||owner.writes()!=expected_writes||
     transmissions!=expected_writes||owner.begin(reserve,clock)||
     owner.mark_export_verified(true))return 1;
  owner.poll(acquire,write,clock,evidence,admitted);
  return transmissions==expected_writes?0:1;
}

#include "park_step_owner.h"
#include <cstdio>
#include <cstring>
#include <string>
using namespace rocell_diag;

struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
static ShoulderPreloadPose pose(unsigned index){
  ShoulderPreloadPose sample;
  const bool after=index>=4;
  sample.started_us=(after?2000000:1000000)+uint64_t(after?index-4:index)*150000;
  sample.finished_us=sample.started_us+50000;
  for(int i=0;i<7;++i){
    sample.goal[i]=ParkStepPolicy::reference_goals[i];
    sample.position[i]=ParkStepPolicy::reference_positions[i];
    sample.torque[i]=1;
  }
  if(after){
    sample.goal[1]=2377;sample.goal[2]=1737;
    sample.position[1]=2378;sample.position[2]=1736;
  }
  for(int i=0;i<7;++i){
    sample.feedback[i][0]=uint8_t(sample.position[i]);
    sample.feedback[i][1]=uint8_t(sample.position[i]>>8);
  }
  return sample;
}
int main(int argc,char** argv){
  if(argc!=2)return 2;
  const std::string mode=argv[1];
  ParkStepOwner owner;Clock clock;unsigned acquisition=0,transmissions=0;
  auto reserve=[](){return true;};
  const uint16_t target=mode=="unbounded_target"?2365:2377;
  if(!owner.begin(target,1737,reserve,clock))return 3;
  auto acquire=[&](ShoulderPreloadPose& out){
    if(acquisition>=(mode=="slow_settle"?8u:7u))return false;
    out=pose(acquisition);
    if(mode=="start_mismatch"&&acquisition==2)out.goal[1]=2388;
    if(mode=="prewrite_changed"&&acquisition==3)out.goal[1]=2388;
    if(mode=="endpoint_wrong"&&acquisition==6)out.goal[1]=2378;
    if(mode=="slow_settle"&&acquisition==4)out.feedback[1][10]=1;
    if(mode=="timeout"&&acquisition>=4){
      out.position[1]=ParkStepPolicy::reference_positions[1];
      out.position[2]=ParkStepPolicy::reference_positions[2];
      out.feedback[1][0]=uint8_t(out.position[1]);out.feedback[1][1]=uint8_t(out.position[1]>>8);
      out.feedback[2][0]=uint8_t(out.position[2]);out.feedback[2][1]=uint8_t(out.position[2]>>8);
    }
    ++acquisition;return true;
  };
  auto write=[&](uint8_t a,uint8_t b,uint16_t x,uint16_t y,uint16_t speed,uint8_t acc){
    if(a!=12||b!=13||x!=2377||y!=1737||speed!=20||acc!=1)return false;
    ++transmissions;return mode!="write_uncertain";
  };
  auto evidence=[&](const char* event,const ShoulderPreloadPose&){
    return !(mode=="evidence_failure"&&std::strcmp(event,"PARK_STEP_INTENT")==0);
  };
  auto admitted=[](){return true;};
  for(unsigned i=0;i<(mode=="slow_settle"?8u:7u)&&owner.state()!=ParkStepOwner::State::Fault&&
                       owner.state()!=ParkStepOwner::State::AwaitExport;++i){
    clock.now=pose(i).finished_us+1000;
    owner.poll(acquire,write,clock,evidence,admitted);
  }
  if(mode=="timeout"){
    clock.now=9000001;owner.poll(acquire,write,clock,evidence,admitted);
    uint8_t boot[16]={},record[1131];
    return owner.state()==ParkStepOwner::State::Fault&&
      std::strcmp(owner.reason(),"ENDPOINT_TIMEOUT")==0&&owner.writes()==1&&
      owner.copy_result(boot,record,sizeof(record))==sizeof(record)?0:1;
  }
  if(mode=="success"||mode=="slow_settle"){
    uint8_t boot[16],record[1131];for(auto& value:boot)value=0xab;
    const size_t size=owner.copy_result(boot,record,sizeof(record));
    if(size!=sizeof(record)||owner.state()!=ParkStepOwner::State::AwaitExport||
       owner.writes()!=1||transmissions!=1||owner.mark_export_verified(false)||
       !owner.mark_export_verified(true)||owner.begin(2377,1737,reserve,clock))return 1;
    for(size_t i=0;i<size;++i)std::printf("%02x",record[i]);
    std::printf("\n");return 0;
  }
  const unsigned expected=(mode=="write_uncertain"||mode=="endpoint_wrong")?1:0;
  if(owner.state()!=ParkStepOwner::State::Fault||owner.writes()!=expected||
     transmissions!=expected||owner.mark_export_verified(true)||
     owner.begin(2377,1737,reserve,clock))return 1;
  return 0;
}

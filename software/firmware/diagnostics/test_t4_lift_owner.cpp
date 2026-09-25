#include <large_pose_relief_owner.h>
#include <cstdio>
#include <cstring>
#include <string>
using namespace rocell_diag;

struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
static ShoulderPreloadPose pose(unsigned index){
  ShoulderPreloadPose sample;const bool after=index>=4;
  sample.started_us=(after?2000000:1000000)+uint64_t(after?index-4:index)*150000;
  sample.finished_us=sample.started_us+50000;
  for(int i=0;i<7;++i){
    sample.goal[i]=after?LargePoseReliefPolicy::target_goals[i]:LargePoseReliefPolicy::source_goals[i];
    sample.position[i]=LargePoseReliefPolicy::source_positions[i];sample.torque[i]=1;
  }
  if(after){sample.position[1]=2225;sample.position[2]=1891;}
  for(int i=0;i<7;++i){sample.feedback[i][0]=uint8_t(sample.position[i]);
    sample.feedback[i][1]=uint8_t(sample.position[i]>>8);}
  return sample;
}
int main(int argc,char** argv){
  if(argc!=2)return 2;const std::string mode=argv[1];
  LargePoseReliefOwner owner;Clock clock;unsigned acquisition=0,transmissions=0;
  auto reserve=[](){return true;};if(!owner.begin(reserve,clock))return 3;
  auto acquire=[&](ShoulderPreloadPose& out){
    if(acquisition>=7)return false;out=pose(acquisition);
    if(mode=="source_rejected"&&acquisition==2)out.goal[1]++;
    if(mode=="prewrite_changed"&&acquisition==3)out.position[0]+=2;
    if(mode=="wrong_goal"&&acquisition==6)out.goal[1]++;
    if(mode=="passive_drift"&&acquisition==6)out.position[4]+=3;
    if(mode=="reverse"&&acquisition>=4)out.position[1]=2295;
    for(int i=0;i<7;++i){out.feedback[i][0]=uint8_t(out.position[i]);
      out.feedback[i][1]=uint8_t(out.position[i]>>8);}
    ++acquisition;return true;
  };
  auto write=[&](uint8_t a,uint8_t b,uint16_t x,uint16_t y,
                 uint16_t speed,uint8_t acc){
    if(a!=12||b!=13||x!=2217||y!=1897||speed!=20||acc!=1)return false;
    ++transmissions;return mode!="write_uncertain";
  };
  auto evidence=[&](const char* event,const ShoulderPreloadPose&){
    return !(mode=="evidence_failure"&&std::strcmp(event,"LARGE_POSE_T4L_INTENT")==0);};
  auto admitted=[](){return true;};
  for(unsigned i=0;i<7&&owner.state()!=LargePoseReliefOwner::State::Fault&&
      owner.state()!=LargePoseReliefOwner::State::AwaitExport;++i){
    clock.now=pose(i).finished_us+1000;owner.poll(acquire,write,clock,evidence,admitted);
  }
  if(mode=="success"){
    uint8_t boot[16],record[1131];for(auto& byte:boot)byte=0xab;
    if(owner.state()!=LargePoseReliefOwner::State::AwaitExport||owner.writes()!=1||
       transmissions!=1||owner.copy_result(boot,record,sizeof(record))!=sizeof(record)||
       owner.mark_export_verified(false)||!owner.mark_export_verified(true)||
       owner.begin(reserve,clock))return 1;
    for(auto byte:record)std::printf("%02x",byte);std::printf("\n");return 0;
  }
  const unsigned expected=mode=="write_uncertain"||mode=="wrong_goal"||
    mode=="passive_drift"||mode=="reverse"?1:0;
  return owner.state()==LargePoseReliefOwner::State::Fault&&owner.writes()==expected&&
    transmissions==expected&&!owner.mark_export_verified(true)&&!owner.begin(reserve,clock)?0:1;
}

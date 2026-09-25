#include "park_reanchor_owner.h"
#include <cstdio>
#include <cstring>
#include <string>
using namespace rocell_diag;

struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
static ShoulderPreloadPose pose(unsigned index,bool no_response=false){
  ShoulderPreloadPose p{};
  const bool after=index>=4;
  p.started_us=(after?2000000:1000000)+
      uint64_t(after?index-4:index)*150000;
  p.finished_us=p.started_us+50000;
  for(int i=0;i<7;++i){
    p.goal[i]=ParkReanchorPolicy::source_goals[i];
    p.position[i]=ParkReanchorPolicy::source_positions[i];
    p.torque[i]=1;
  }
  if(after){
    p.goal[1]=ParkReanchorPolicy::target12;
    p.goal[2]=ParkReanchorPolicy::target13;
    if(!no_response){
#ifdef ROCELL_PARK_REANCHOR_POLICY_HEADER
      p.position[1]=ParkReanchorPolicy::expected12;
      p.position[2]=ParkReanchorPolicy::expected13;
#else
      p.position[1]=ParkReanchorPolicy::target12;
      p.position[2]=ParkReanchorPolicy::target13;
#endif
    }
  }
  for(int i=0;i<7;++i){
    p.feedback[i][0]=uint8_t(p.position[i]);
    p.feedback[i][1]=uint8_t(p.position[i]>>8);
  }
  return p;
}

int main(int argc,char** argv){
  if(argc!=2)return 2;
  const std::string mode=argv[1];
  ParkReanchorOwner owner;Clock clock;
  unsigned acquisitions=0,transmissions=0;
  auto reserve=[](){return true;};
  if(!owner.begin(reserve,clock))return 3;
  auto acquire=[&](ShoulderPreloadPose& out){
    if(mode=="feedback_failed"&&acquisitions==4)return false;
    out=pose(acquisitions,mode=="timeout");
    if(mode=="start_mismatch"&&acquisitions==2)out.goal[1]=2376;
    if(mode=="prewrite_changed"&&acquisitions==3)out.position[1]=2383;
    if(mode=="out_of_bounds"&&acquisitions==4)
      out.position[1]=ParkReanchorPolicy::source_positions[1]+
                      ParkReanchorPolicy::maximum_travel+1;
    for(int i=0;i<7;++i){
      out.feedback[i][0]=uint8_t(out.position[i]);
      out.feedback[i][1]=uint8_t(out.position[i]>>8);
    }
    ++acquisitions;return true;
  };
  auto write=[&](uint8_t a,uint8_t b,uint16_t x,uint16_t y,uint16_t speed,uint8_t acc){
    if(a!=12||b!=13||x!=ParkReanchorPolicy::target12||
       y!=ParkReanchorPolicy::target13||speed!=20||acc!=1)return false;
    ++transmissions;return mode!="write_uncertain";
  };
  auto evidence=[](const char*,const ShoulderPreloadPose&){return true;};
  auto admitted=[](){return true;};
  for(unsigned i=0;i<7&&owner.state()!=ParkReanchorOwner::State::Fault&&
                       owner.state()!=ParkReanchorOwner::State::AwaitExport;++i){
    clock.now=pose(i).finished_us+1000;
    owner.poll(acquire,write,clock,evidence,admitted);
  }
  if(mode=="timeout"){
    clock.now=9000001;
    owner.poll(acquire,write,clock,evidence,admitted);
  }
  if(mode=="success"){
    if(owner.state()!=ParkReanchorOwner::State::AwaitExport||
       owner.writes()!=1||transmissions!=1||owner.postwrite_samples()!=3)
      return 4;
  }else{
    const unsigned expected=(mode=="start_mismatch"||mode=="prewrite_changed")?0:1;
    if(owner.state()!=ParkReanchorOwner::State::Fault||
       owner.writes()!=expected||transmissions!=expected)return 5;
  }
  uint8_t boot[16]={},record[ParkReanchorOwner::record_size];
  const size_t size=owner.copy_result(boot,record,sizeof(record));
  if(owner.writes()==1){
    if(size!=sizeof(record)||std::memcmp(record,"RCRTN00001",10)!=0||
       record[26]==0||record[36]!=1)return 6;
    if(mode=="write_uncertain"&&record[27]!=0)return 7;
    if(mode=="success"&&(record[26]!=1||record[27]!=3))return 8;
    if(mode=="out_of_bounds"&&(record[26]!=3||record[27]!=1))return 9;
    if(mode=="timeout"&&(record[26]!=2||record[27]!=3))return 10;
  }else if(size!=0)return 11;
  if(mode=="success"){
    if(owner.mark_export_verified(false)||!owner.mark_export_verified(true)||
       owner.begin(reserve,clock))return 12;
  }else if(owner.mark_export_verified(true)||owner.begin(reserve,clock))return 13;
  if(mode=="success"||mode=="timeout"){
    for(size_t i=0;i<size;++i)std::printf("%02x",record[i]);
    std::printf("\n");
  }
  return 0;
}

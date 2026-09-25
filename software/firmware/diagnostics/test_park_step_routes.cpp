#include <functional>
#include <map>
#include <string>
#include <cassert>
#include <cstdint>
constexpr int HTTP_GET=0,HTTP_POST=1;
#include "park_step_routes.h"
using namespace rocell_diag;
struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
struct Crypto {
  bool sha256(const uint8_t* bytes,size_t count,uint8_t (&out)[32]){
    for(unsigned i=0;i<32;++i)out[i]=uint8_t(i);
    for(size_t i=0;i<count;++i)out[i%32]^=bytes[i];return true;
  }
};
struct Services {
  bool reserved=false,stall=false;unsigned samples=0,writes=0;
  bool reserve(){if(reserved)return false;return reserved=true;}
  bool owned(){return reserved;}
  bool healthy(){return true;}
  bool park_step_evidence(const char*,const ShoulderPreloadPose&){return true;}
  bool park_step_write(uint8_t a,uint8_t b,uint16_t x,uint16_t y,uint16_t speed,uint8_t acc){
    assert(a==12&&b==13&&x==2377&&y==1737&&speed==20&&acc==1);
    ++writes;return true;
  }
  bool park_step_sample(ShoulderPreloadPose& p){
    if(samples>=7)return false;
    unsigned index=samples++;bool after=index>=4;
    p.started_us=(after?2000000:1000000)+uint64_t(after?index-4:index)*150000;
    p.finished_us=p.started_us+50000;
    for(int i=0;i<7;++i){
      p.goal[i]=ParkStepPolicy::reference_goals[i];
      p.position[i]=ParkStepPolicy::reference_positions[i];p.torque[i]=1;
    }
    if(after){p.goal[1]=2377;p.goal[2]=1737;
      if(!stall){p.position[1]=2378;p.position[2]=1736;}}
    for(int i=0;i<7;++i){
      p.feedback[i][0]=uint8_t(p.position[i]);p.feedback[i][1]=uint8_t(p.position[i]>>8);
    }
    return true;
  }
};
struct Web {
  std::map<std::string,std::function<void()>> routes;
  std::string body,response;int status=0;
  template<class Handler>void on(const char* path,int,Handler handler){routes[path]=handler;}
  int args(){return body.empty()?0:1;}
  std::string argName(int){return "plain";}
  std::string arg(const char*){return body;}
  void send(int code,const char*,const char* text){status=code;response=text;}
};
int main(){
  Crypto crypto;Services services;Clock clock;Web web;uint8_t boot[16]={};
  ParkStepRoutes<Crypto,Services,Clock,Web> routes(crypto,services,clock,web,boot);
  routes.register_routes();assert(web.routes.size()==4&&services.samples==0&&services.writes==0);
  web.body="2365,1749";web.routes["/rocell/park-step/start"]();
  assert(web.status==202); // Owner rechecks fresh start before any write.
  for(unsigned i=0;i<7&&services.samples<3;++i){
    clock.now=1000000+uint64_t(i)*150000+51000;routes.poll();
  }
  assert(services.writes==0); // Wrong next-step target from reference fails.
  web.body.clear();web.routes["/rocell/park-step/start"]();assert(web.status==400);

  Services fresh;Web other;ParkStepRoutes<Crypto,Services,Clock,Web> run(crypto,fresh,clock,other,boot);
  run.register_routes();
  other.body="2389,1725";other.routes["/rocell/park-step/start"]();
  assert(other.status==400&&!fresh.reserved);
  other.body="2377,1738";other.routes["/rocell/park-step/start"]();
  assert(other.status==400&&!fresh.reserved);
  other.body="2377,1737";clock.now=900000;
  other.routes["/rocell/park-step/start"]();assert(other.status==202);
  for(unsigned i=0;i<7;++i){
    clock.now=(i>=4?2000000:1000000)+uint64_t(i>=4?i-4:i)*150000+51000;
    run.poll();
  }
  assert(fresh.writes==1&&fresh.samples==7);
  other.body.clear();other.routes["/rocell/park-step/record"]();
  assert(other.status==200&&other.response.size()==2262);
  std::string record=other.response;uint8_t digest[32],raw[1131];
  for(size_t i=0;i<1131;++i){raw[i]=uint8_t(std::stoul(record.substr(2*i,2),nullptr,16));}
  crypto.sha256(raw,sizeof(raw),digest);
  other.body=std::string(64,'0');other.routes["/rocell/park-step/receipt"]();
  assert(other.status==409);
  static const char digits[]="0123456789abcdef";other.body.clear();
  for(auto b:digest){other.body+=digits[b>>4];other.body+=digits[b&15];}
  other.routes["/rocell/park-step/receipt"]();assert(other.status==200);
  other.body="2377,1737";other.routes["/rocell/park-step/start"]();
  assert(other.status==409&&fresh.writes==1);

  // A bounded no-progress timeout retains the raw samples for diagnosis,
  // while refusing the success receipt and any second write.
  Services stalled;stalled.stall=true;Web fault_web;
  ParkStepRoutes<Crypto,Services,Clock,Web> fault(crypto,stalled,clock,fault_web,boot);
  fault.register_routes();fault_web.body="2377,1737";clock.now=900000;
  fault_web.routes["/rocell/park-step/start"]();assert(fault_web.status==202);
  for(unsigned i=0;i<7;++i){
    clock.now=(i>=4?2000000:1000000)+uint64_t(i>=4?i-4:i)*150000+51000;
    fault.poll();
  }
  clock.now=9000001;fault.poll();fault_web.body.clear();
  fault_web.routes["/rocell/park-step/status"]();
  assert(fault_web.response=="ENDPOINT_TIMEOUT|1");
  fault_web.routes["/rocell/park-step/record"]();
  assert(fault_web.status==200&&fault_web.response.size()==2262);
  fault_web.body=std::string(64,'0');fault_web.routes["/rocell/park-step/receipt"]();
  assert(fault_web.status==409&&stalled.writes==1);
}

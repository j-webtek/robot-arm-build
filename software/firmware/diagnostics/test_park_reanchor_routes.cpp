#include <cassert>
#include <cstdint>
#include <functional>
#include <map>
#include <string>
constexpr int HTTP_GET=0,HTTP_POST=1;
#include "park_reanchor_routes.h"
using namespace rocell_diag;

struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
struct Crypto {
  bool sha256(const uint8_t* bytes,size_t count,uint8_t (&out)[32]){
    for(unsigned i=0;i<32;++i)out[i]=uint8_t(i);
    for(size_t i=0;i<count;++i)out[i%32]^=bytes[i];return true;
  }
};
struct Services {
  bool reserved=false,no_response=false;
  unsigned samples=0,writes=0;
  bool reserve(){if(reserved)return false;return reserved=true;}
  bool owned(){return reserved;}
  bool healthy(){return true;}
  bool park_return_evidence(const char*,const ShoulderPreloadPose&){return true;}
  bool park_return_write(uint8_t a,uint8_t b,uint16_t x,uint16_t y,
                         uint16_t speed,uint8_t acc){
    assert(a==12&&b==13&&x==2389&&y==1725&&speed==20&&acc==1);
    ++writes;return true;
  }
  bool park_return_sample(ShoulderPreloadPose& p){
    if(samples>=7)return false;
    const unsigned index=samples++;
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
      p.goal[1]=2389;p.goal[2]=1725;
      if(!no_response){p.position[1]=2389;p.position[2]=1725;}
    }
    for(int i=0;i<7;++i){
      p.feedback[i][0]=uint8_t(p.position[i]);
      p.feedback[i][1]=uint8_t(p.position[i]>>8);
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
  void send(int code,const char*,const char* value){status=code;response=value;}
};
int main(int argc,char** argv){
  assert(argc==2);
  Crypto crypto;Services services;Clock clock;Web web;uint8_t boot[16]={};
  services.no_response=std::string(argv[1])=="fault";
  ParkReanchorRoutes<Crypto,Services,Clock,Web> route(crypto,services,clock,web,boot);
  route.register_routes();route.register_routes();
  assert(web.routes.size()==4&&services.samples==0&&services.writes==0);
  web.body="2389,1725";web.routes["/rocell/park-return/start"]();
  assert(web.status==400&&!services.reserved);
  web.body.clear();web.routes["/rocell/park-return/start"]();
  assert(web.status==202);
  for(unsigned i=0;i<7;++i){
    clock.now=(i>=4?2000000:1000000)+
        uint64_t(i>=4?i-4:i)*150000+51000;
    route.poll();
  }
  if(services.no_response){clock.now=9000001;route.poll();}
  assert(services.samples==7&&services.writes==1);
  web.routes["/rocell/park-return/status"]();
  assert(web.status==200&&web.response.find("|1")!=std::string::npos);
  web.routes["/rocell/park-return/record"]();
  assert(web.status==200&&
         web.response.size()==2*ParkReanchorOwner::record_size);
  std::string text=web.response;
  uint8_t raw[ParkReanchorOwner::record_size],digest[32];
  for(size_t i=0;i<sizeof(raw);++i)
    raw[i]=uint8_t(std::stoul(text.substr(2*i,2),nullptr,16));
  assert(raw[26]==(services.no_response?2:1));
  crypto.sha256(raw,sizeof(raw),digest);
  static const char digits[]="0123456789abcdef";
  for(auto value:digest){web.body+=digits[value>>4];web.body+=digits[value&15];}
  web.routes["/rocell/park-return/receipt"]();
  assert(web.status==(services.no_response?409:200));
  web.body.clear();web.routes["/rocell/park-return/start"]();
  assert(web.status==409);
  route.poll();assert(services.writes==1);
  return 0;
}

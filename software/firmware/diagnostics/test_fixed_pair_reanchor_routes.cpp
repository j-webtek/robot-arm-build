#include <functional>
#include <map>
#include <string>
#include <cassert>
#include <cstdint>
constexpr int HTTP_GET=0,HTTP_POST=1;
#include "fixed_pair_reanchor_routes.h"
using namespace rocell_diag;
struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
struct Crypto {
  bool sha256(const uint8_t* bytes,size_t count,uint8_t (&out)[32]){
    for(unsigned i=0;i<32;++i)out[i]=uint8_t(i);
    for(size_t i=0;i<count;++i)out[i%32]^=bytes[i];return true;
  }
};
struct Services {
  bool reserved=false;unsigned samples=0,writes=0;
  bool reserve(){if(reserved)return false;return reserved=true;}
  bool owned(){return reserved;}
  bool healthy(){return true;}
  bool reanchor_evidence(const char*,const ShoulderPreloadPose&){return true;}
  bool reanchor_write(uint8_t a,uint8_t b,uint16_t x,uint16_t y,uint16_t speed,uint8_t acc){
    assert(a==12&&b==13&&x==2389&&y==1725&&speed==20&&acc==1);
    ++writes;return true;
  }
  bool reanchor_sample(ShoulderPreloadPose& p){
    if(samples>=7)return false;
    unsigned index=samples++;bool after=index>=4;
    p.started_us=(after?2000000:1000000)+uint64_t(after?index-4:index)*150000;
    p.finished_us=p.started_us+50000;
    for(int i=0;i<7;++i){p.goal[i]=p.position[i]=2000;p.torque[i]=1;}
    p.goal[1]=after?2389:2386;p.goal[2]=after?1725:1728;
    p.position[1]=after?2391:2390;p.position[2]=after?1724:1725;
    for(int i=0;i<7;++i){p.feedback[i][0]=uint8_t(p.position[i]);p.feedback[i][1]=uint8_t(p.position[i]>>8);}
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
  FixedPairReanchorRoutes<Crypto,Services,Clock,Web> routes(crypto,services,clock,web,boot);
  routes.register_routes();assert(web.routes.size()==4&&services.samples==0&&services.writes==0);
  web.body="2389,1725";web.routes["/rocell/reanchor/start"]();assert(web.status==400&&!services.reserved);
  web.body.clear();web.routes["/rocell/reanchor/start"]();assert(web.status==202);
  for(unsigned i=0;i<7;++i){
    clock.now=(i>=4?2000000:1000000)+uint64_t(i>=4?i-4:i)*150000+51000;
    routes.poll();
  }
  assert(services.writes==1&&services.samples==7);
  web.routes["/rocell/reanchor/record"]();assert(web.status==200&&web.response.size()==2254);
  std::string record=web.response;uint8_t digest[32];uint8_t raw[1127];
  for(size_t i=0;i<1127;++i){auto hex=record.substr(2*i,2);raw[i]=uint8_t(std::stoul(hex,nullptr,16));}
  crypto.sha256(raw,sizeof(raw),digest);
  web.body=std::string(64,'0');web.routes["/rocell/reanchor/receipt"]();assert(web.status==409);
  static const char digits[]="0123456789abcdef";web.body.clear();
  for(auto b:digest){web.body+=digits[b>>4];web.body+=digits[b&15];}
  web.routes["/rocell/reanchor/receipt"]();assert(web.status==200);
  web.body.clear();web.routes["/rocell/reanchor/start"]();assert(web.status==409);
  routes.poll();assert(services.writes==1);
}

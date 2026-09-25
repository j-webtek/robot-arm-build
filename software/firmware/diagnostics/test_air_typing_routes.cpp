#include <functional>
#include <map>
#include <string>
#include <cassert>
#include <cstdint>
constexpr int HTTP_GET=0,HTTP_POST=1;
#include "air_typing_routes.h"
using namespace rocell_diag;
struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
struct Crypto {
  bool sha256(const uint8_t* bytes,size_t count,uint8_t (&out)[32]){
    for(unsigned i=0;i<32;++i)out[i]=uint8_t(i);
    for(size_t i=0;i<count;++i)out[i%32]^=bytes[i];return true;
  }
};
struct Services {
  Clock& clock;bool reserved=false;unsigned writes=0;
  uint16_t pos[7]={2047,2225,1890,2716,1979,2041,2047};
  uint16_t goals[7]={2047,2217,1897,2711,1980,2040,2047};
  const int residual[7]={0,8,-7,5,-1,1,0};
  bool reserve(){if(reserved)return false;return reserved=true;}
  bool owned(){return reserved;}bool healthy(){return true;}
  bool memory_fits(size_t,size_t){return true;}
  bool air_typing_evidence(const char*,const ShoulderPreloadPose&){return true;}
  bool air_typing_write(const uint16_t (&target)[7],uint16_t speed,uint8_t acc){
    assert(speed==20&&acc==1);
    for(int i=0;i<7;++i){assert(target[i]==AirTypingPolicy::targets[writes][i]);
      goals[i]=target[i];pos[i]=uint16_t(int(target[i])+residual[i]);}
    ++writes;return true;
  }
  bool air_typing_sample(ShoulderPreloadPose& p){
    p={};p.started_us=clock.now-50000;p.finished_us=clock.now;
    for(int i=0;i<7;++i){p.goal[i]=goals[i];p.position[i]=pos[i];p.torque[i]=1;
      p.feedback[i][0]=uint8_t(pos[i]);p.feedback[i][1]=uint8_t(pos[i]>>8);}
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
  Crypto crypto;Clock clock;Services services{clock};Web web;uint8_t boot[16]={};
  AirTypingRoutes<Crypto,Services,Clock,Web> routes(crypto,services,clock,web,boot);
  routes.register_routes();assert(web.routes.size()==5&&!services.reserved);
  auto request=[&](const char* action,std::string body=""){
    web.body=body;web.routes[std::string("/rocell/air-type/")+action]();
  };
  request("start","BAD");assert(web.status==400&&!services.reserved);
  request("next","2");assert(web.status!=202&&!services.reserved);
  request("start","AIR17");assert(web.status==202);
  for(unsigned leg=1;leg<=AirTypingPolicy::legs;++leg){
    for(unsigned n=0;n<7;++n){clock.now+=150000;routes.poll();}
    assert(services.writes==leg);
    request("status");assert(web.response=="AWAITING_EXPORT|"+std::to_string(leg));
    request("record");assert(web.status==200&&web.response.size()==2260);
    auto encoded=web.response;uint8_t raw[1130],digest[32];
    for(size_t i=0;i<1130;++i)raw[i]=uint8_t(std::stoul(encoded.substr(2*i,2),nullptr,16));
    crypto.sha256(raw,sizeof(raw),digest);
    std::string receipt=std::to_string(leg)+":";const char* digits="0123456789abcdef";
    for(auto b:digest){receipt+=digits[b>>4];receipt+=digits[b&15];}
    request("receipt",std::to_string(leg)+":"+std::string(64,'0'));assert(web.status==409);
    request("receipt",receipt);assert(web.status==200);
    assert(web.response==(leg==AirTypingPolicy::legs?"COMPLETE":"READY|"+std::to_string(leg+1)));
    routes.poll();assert(services.writes==leg);
    request("receipt",receipt);assert(web.status==409);
    if(leg<AirTypingPolicy::legs){
      request("next",std::to_string(leg));assert(web.status==400);
      request("next",std::to_string(leg+1));assert(web.status==202);
      request("next",std::to_string(leg+1));assert(web.status==409);
    }
  }
  request("start","AIR17");assert(web.status==409);
  routes.poll();assert(services.writes==AirTypingPolicy::legs);
}

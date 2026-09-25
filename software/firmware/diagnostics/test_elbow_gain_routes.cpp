#define main acquisition_cases
#include "test_elbow_gain_snapshot.cpp"
#undef main
#include <map>
#include <string>
#include <functional>
constexpr int HTTP_GET=0,HTTP_POST=1;
#include "elbow_gain_routes.h"
struct Web {
  std::map<std::string,std::function<void()>> routes;
  std::map<std::string,int> methods;int code=0,parameters=0;std::string body;
  void on(const char* path,int method,std::function<void()> callback){routes[path]=callback;methods[path]=method;}
  int args(){return parameters;}
  void sendHeader(const char*,const char*){}
  void send(int status,const char*,const char* bytes){code=status;body=bytes;}
};
int main(){
  for(int failure=-1;failure<3;++failure){
    ReadOnlyBus bus;bus.fail_at=failure;Clock clock;Web web;bool idle=false;
    rocell_diag::ElbowGainRoutes<ReadOnlyBus,Clock,Web> routes(
        bus,clock,web,"11111111111111111111111111111111",inactive,&idle);
    routes.register_routes();routes.register_routes();assert(web.routes.size()==2&&bus.calls==0);
    auto capture=web.routes.at("/rocell/elbow-gain/capture");
    auto result=web.routes.at("/rocell/elbow-gain/result");
    assert(web.methods.at("/rocell/elbow-gain/capture")==HTTP_POST);
    result();assert(web.code==404&&bus.calls==0);
    capture();assert(web.code==409&&bus.calls==0);
    idle=true;web.parameters=1;capture();assert(web.code==400&&bus.calls==0);
    web.parameters=0;capture();assert(web.code==200);
    const auto saved=web.body;const auto calls=bus.calls;
    JsonDocument doc;assert(!deserializeJson(doc,saved));assert(doc["complete"].as<bool>()==(failure==-1));
    capture();assert(web.code==409&&bus.calls==calls);
    idle=false;result();assert(web.code==200&&web.body==saved&&bus.calls==calls);
  }
}

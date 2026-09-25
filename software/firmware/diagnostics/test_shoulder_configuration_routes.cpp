#define main acquisition_cases
#include "test_shoulder_configuration_snapshot.cpp"
#undef main
#include <map>
#include <string>
#include <functional>
constexpr int HTTP_GET=0,HTTP_POST=1;
#include "shoulder_configuration_routes.h"
struct Web {
 std::map<std::string,std::function<void()>> routes;
 std::map<std::string,int> methods;int code=0,parameters=0;std::string body;
 void on(const char* path,int method,std::function<void()> fn){routes[path]=fn;methods[path]=method;}
 int args(){return parameters;}
 void sendHeader(const char*,const char*){}
 void send(int status,const char*,const char* bytes){code=status;body=bytes;}
};
bool allowed(void* value){return *static_cast<bool*>(value);}
int main(){
 for(int failure=-1;failure<34;++failure){
  ReadOnlyBus bus;bus.fail=failure;Clock clock;Web web;bool idle=false;
  rocell_diag::ShoulderConfigurationRoutes<ReadOnlyBus,Clock,Web> routes(
    bus,clock,web,"abababababababababababababababab",allowed,&idle);
  routes.register_routes();routes.register_routes();assert(web.routes.size()==2&&bus.calls==0);
  auto capture=web.routes.at("/rocell/shoulder-configuration/capture");
  auto result=web.routes.at("/rocell/shoulder-configuration/result");
  assert(web.methods.at("/rocell/shoulder-configuration/capture")==HTTP_POST);
  assert(web.methods.at("/rocell/shoulder-configuration/result")==HTTP_GET);
  result();assert(web.code==404&&bus.calls==0);
  capture();assert(web.code==409&&bus.calls==0);
  idle=true;web.parameters=1;capture();assert(web.code==400&&bus.calls==0);
  web.parameters=0;capture();assert(web.code==200);
  const auto saved=web.body;const auto calls=bus.calls;
  JsonDocument doc;assert(!deserializeJson(doc,saved));assert(doc["complete"].as<bool>()==(failure==-1));
  assert(doc["reads"].size()==(failure<0?34:failure+1));
  capture();assert(web.code==409&&bus.calls==calls);
  idle=false;result();assert(web.code==200&&web.body==saved&&bus.calls==calls);
 }
 std::cout<<"SHOULDER_ROUTES_READ_ONLY_PASSED\n";
}

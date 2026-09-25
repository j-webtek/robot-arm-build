#include <cassert>
#include <cstring>
#include <string>
#include <map>
#include <functional>
constexpr int HTTP_GET=0,HTTP_POST=1;
#include "configured_recovery_routes.h"
struct Web {
  std::map<std::string,std::function<void()>> routes;
  std::map<std::string,int> methods;
  int parameters=0,code=0;std::string query,body;
  void on(const char* path,int method,std::function<void()> cb){routes[path]=cb;methods[path]=method;}
  int args(){return parameters;}
  std::string arg(const char*){return query;}
  void sendHeader(const char*,const char*){}
  void send(int c,const char*,const char* b){code=c;body=b;}
};
struct Runtime {
  bool active=false,serialize=true;int reads=0,faults=0;
  bool exclusive_work(){return active;}
  size_t size(){return 8;}
  void interference(){++faults;}
  void export_failed(){++faults;}
  bool status_json(char* out,size_t n){++reads;snprintf(out,n,"{\"status\":true}");return serialize;}
  bool record_json(size_t,char* out,size_t n){++reads;snprintf(out,n,"{\"record\":true}");return serialize;}
};
struct Prepare {
  int calls=0;bool success=true;
  bool operator()(char* out,size_t n){++calls;snprintf(out,n,"{\"challenge\":true}");return success;}
};
int main(){
  for(bool success:{false,true}){
    Runtime runtime;Prepare prepare;prepare.success=success;Web web;
    rocell_diag::ConfiguredRecoveryRoutes<Runtime,Prepare,Web> routes(runtime,prepare,web);
    routes.register_routes();routes.register_routes();assert(web.routes.size()==3&&prepare.calls==0);
    auto start=web.routes.at("/rocell/recovery/prepare");
    auto status=web.routes.at("/rocell/recovery/status");
    auto record=web.routes.at("/rocell/recovery/record");
    assert(web.methods.at("/rocell/recovery/prepare")==HTTP_POST);
    status();assert(web.code==503&&runtime.reads==0);
    web.parameters=1;start();assert(web.code==400&&prepare.calls==0);
    web.parameters=0;start();assert(web.code==(success?200:503)&&prepare.calls==1);
    start();assert(web.code==409&&prepare.calls==1);
    if(!success){assert(runtime.faults==1);continue;}
    runtime.active=true;status();assert(web.code==409&&runtime.reads==0);
    runtime.active=false;status();assert(web.code==200&&runtime.reads==1);
    web.parameters=1;
    for(const char* invalid:{"","00","-1","1a","123"}){
      web.query=invalid;record();assert(web.code==400&&runtime.reads==1);
    }
    web.query="8";record();assert(web.code==404&&runtime.reads==1);
    web.query="0";record();assert(web.code==200&&runtime.reads==2);
    runtime.serialize=false;record();assert(web.code==500&&runtime.faults==1);
  }
}

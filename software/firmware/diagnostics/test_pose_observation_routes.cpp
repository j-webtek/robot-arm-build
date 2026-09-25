#include <cassert>
#include <map>
#include <functional>
#include <string>
constexpr int HTTP_POST=1,HTTP_GET=0;
#include "pose_observation_routes.h"
struct Web {
  std::map<std::string,std::function<void()>> routes;
  std::string request,query,body;int parameters=0,code=0;
  void on(const char* p,int,std::function<void()> cb){routes[p]=cb;}
  std::string arg(const char* name){return std::string(name)=="plain"?request:query;}
  int args(){return parameters;}
  void sendHeader(const char*,const char*){}
  void send(int c,const char*,const char* text){code=c;body=text;}
};
struct Owner {
  int requests=0,reads=0;bool running=false,fault=false;
  bool request(const char* boot,const char* id){++requests;
    if(requests!=1||strcmp(boot,"boot")||strcmp(id,"scan"))return false;
    running=true;return true;}
  bool active(){return running;}
  bool export_fault(){return fault;}
  const char* record(size_t i){++reads;return i==0?"{\"retained\":true}":nullptr;}
};
int main(){
  Owner owner;Web web;rocell_diag::PoseObservationRoutes<Owner,Web> routes(owner,web);
  routes.register_routes();routes.register_routes();assert(web.routes.size()==2);
  auto capture=web.routes.at("/rocell/pose/capture");auto record=web.routes.at("/rocell/pose/record");
  for(const char* bad:{"","{}","{\"boot_id\":1,\"scan_id\":\"scan\"}",
      "{\"boot_id\":\"boot\",\"boot_id\":\"other\",\"scan_id\":\"scan\"}"}){
    web.request=bad;capture();assert(web.code==400&&owner.requests==0);}
  web.request="{\"boot_id\":\"boot\",\"scan_id\":\"scan\"}";
  capture();assert(web.code==202&&owner.requests==1&&owner.reads==0);
  capture();assert(web.code==409);
  web.parameters=1;web.query="0";record();assert(web.code==409&&owner.reads==0);
  owner.running=false;record();assert(web.code==200&&owner.reads==1);
  for(const char* bad:{"","00","-1","4"}){web.query=bad;record();assert(web.code==400);}
  web.query="3";record();assert(web.code==404);
  owner.fault=true;web.query="0";record();assert(web.code==500);
}

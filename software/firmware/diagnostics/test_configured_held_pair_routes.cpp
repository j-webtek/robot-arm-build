#include <cassert>
#include <cstring>
#include <string>
#include <map>
#include <functional>
constexpr int HTTP_GET=0,HTTP_POST=1;
#include "configured_held_pair_routes.h"
struct Web {
  std::map<std::string,std::function<void()>> routes;std::map<std::string,int> methods;
  int code=0,polls=0;std::string body,query,cache;
  void on(const char* path,int method,std::function<void()> fn){routes[path]=fn;methods[path]=method;}
  void sendHeader(const char*,const char* value){cache=value;}
  void send(int value,const char*,const char* bytes){code=value;body=bytes;}
  std::string arg(const char*){return query;}
  void handleClient(){++polls;}
};
struct Pair {
  int initial=0,reverse=0,polls=0,failures=0;bool active=false,return_ready=false,serialize=true;
  bool issue_initial(char* out,size_t n){++initial;snprintf(out,n,"{\"initial\":true}");active=true;return true;}
  bool issue_return(char* out,size_t n){++reverse;if(!return_ready)return false;
    snprintf(out,n,"{\"return\":true}");active=true;return true;}
  bool exclusive_work()const{return active;}
  bool status_json(char* out,size_t n){snprintf(out,n,"{\"state\":true}");return serialize;}
  size_t record_count()const{return 7;}
  bool record_json(size_t,char* out,size_t n){snprintf(out,n,"{\"record\":true}");return serialize;}
  void export_failed(){++failures;}
  void poll(){++polls;}
};
struct Hold {int polls=0;bool active=false;void poll(){++polls;}bool exclusive_work(){return active;}};
int main(){
 for(int failure=0;failure<3;++failure){
  Pair pair;Web web;Hold hold;int prepared=0;
  auto prepare=[&](){++prepared;return failure!=1;};
  rocell_diag::ConfiguredHeldPairRoutes<Pair,decltype(prepare),Web> routes(pair,prepare,web);
  routes.register_routes();routes.register_routes();
  assert(prepared==0&&pair.initial==0&&web.routes.size()==4);
  assert(web.methods["/rocell/held-pair/prepare"]==HTTP_POST);
  assert(web.methods["/rocell/held-pair/return-challenge"]==HTTP_POST);
  auto start=web.routes.at("/rocell/held-pair/prepare");
  auto status=web.routes.at("/rocell/held-pair/status");
  auto record=web.routes.at("/rocell/held-pair/record");
  auto back=web.routes.at("/rocell/held-pair/return-challenge");
  status();assert(web.code==503);start();assert(web.code==(failure==1?503:200));
  start();assert(web.code==409&&prepared==1&&pair.initial==(failure==1?0:1));
  if(failure==1)continue;
  rocell_diag::poll_hold_pair_diagnostics(hold,pair,web);
  assert(web.polls==0&&pair.polls==1&&hold.polls==1);
  status();assert(web.code==409);
  pair.active=false;hold.active=true;
  rocell_diag::poll_hold_pair_diagnostics(hold,pair,web);assert(web.polls==0);
  hold.active=false;
  rocell_diag::poll_hold_pair_diagnostics(hold,pair,web);assert(web.polls==1);
  status();assert(web.code==200);
  for(const char* query:{"","-1","00","a","123"}){web.query=query;record();assert(web.code==400);}
  web.query="34";record();assert(web.code==404);
  web.query="0";record();assert(web.code==200&&web.cache=="no-store");
  pair.serialize=false;record();assert(web.code==500&&pair.failures==1);pair.serialize=true;
  pair.return_ready=failure!=2;back();assert(web.code==(failure==2?409:200));
  pair.active=false;back();assert(web.code==409&&pair.reverse==1);
 }
}

#include <map>
#include <functional>
#include <string>
#include <cassert>
constexpr int HTTP_GET=0,HTTP_POST=1;
#include "characterization_routes.h"
#include "characterization_prepare_routes.h"
struct Web {
 std::map<std::string,std::function<void()>> routes;
 int parameters=0,status=0;std::string name="plain",body,response;
 void on(const char* p,int,std::function<void()> f){routes[p]=f;}
 int args(){return parameters;}std::string argName(int){return name;}std::string arg(const char*){return body;}
 void sendHeader(const char*,const char*){}
 void send(int s,const char*,const char* text){status=s;response=text;}
};
struct Transport {
 unsigned calls=0;size_t size=0;rocell_diag::CampaignRequest request;
 int dispatch(rocell_diag::CampaignRequest r,const uint8_t*,size_t n,uint8_t* out,size_t,size_t& written){
   ++calls;size=n;request=r;written=1024;memset(out,0xab,written);return 200;
 }
};
struct Controller {
 unsigned calls=0;
 struct Session{unsigned completed(){return 0;}unsigned writes(){return 0;}};
 bool prepare(const uint16_t (&bounds)[7][2]){assert(bounds[0][1]==4095);return ++calls==1;}
 Session* session(){return nullptr;}
 const char* state_name(){return calls?"CAPTURING":"NEW";}
 size_t publish_challenge(uint8_t*,size_t){return 0;}
 size_t publish_reference(uint8_t*,size_t){return 0;}
};
int main(){
 Web web;Transport transport;bool allowed=false;auto auth=[&](){return allowed;};
 rocell_diag::CharacterizationRoutes<Transport,decltype(auth),Web> routes(transport,auth,web);
 routes.register_routes();routes.register_routes();assert(web.routes.size()==5&&!transport.calls);
 auto start=web.routes.at("/rocell/characterization/start");
 start();assert(web.status==403&&!transport.calls);allowed=true;
 start();assert(web.status==400&&!transport.calls);
 web.parameters=1;web.body="0g";start();assert(web.status==400&&!transport.calls);
 web.body=std::string(1026,'a');start();assert(web.status==400&&!transport.calls);
 web.body="0102";start();assert(web.status==200&&transport.calls==1&&transport.size==2);
 assert(web.response.size()==2048&&web.response.substr(0,4)=="abab");
 web.routes.at("/rocell/characterization/record-info")();assert(web.status==400&&transport.calls==1);
 web.parameters=0;web.routes.at("/rocell/characterization/record-info")();assert(transport.calls==2);
 allowed=false;web.routes.at("/rocell/characterization/fault")();assert(web.status==403&&transport.calls==2);
 Controller controller;uint16_t bounds[7][2];for(auto& b:bounds){b[0]=0;b[1]=4095;}
 rocell_diag::CharacterizationPrepareRoutes<Controller,decltype(auth),Web> prep(controller,auth,web,bounds);
 prep.register_routes();prep.register_routes();assert(web.routes.size()==9);
 bounds[0][1]=1; // Adapter owns its reviewed copy.
 auto prepare=web.routes.at("/rocell/characterization/prepare");
 prepare();assert(web.status==403&&controller.calls==0);
 allowed=true;web.parameters=1;prepare();assert(web.status==400&&controller.calls==0);
 web.parameters=0;prepare();assert(web.status==202&&controller.calls==1);
 web.routes.at("/rocell/characterization/status")();assert(web.status==200&&web.response.find("CAPTURING")!=std::string::npos);
 prepare();assert(web.status==409);
 web.routes.at("/rocell/characterization/challenge")();assert(web.status==409);
 web.routes.at("/rocell/characterization/reference")();assert(web.status==409);
 allowed=false;web.routes.at("/rocell/characterization/reference")();assert(web.status==403);
}

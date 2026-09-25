#include <cassert>
#include <map>
#include <functional>
#include <string>
#include <iostream>
constexpr int HTTP_GET=0,HTTP_POST=1;
#include "shoulder_session_routes.h"
struct Clock {uint64_t now_us(){return 1000;}};
struct Session {
 rocell_diag::ShoulderPreloadPhase state=rocell_diag::ShoulderPreloadPhase::Waiting;
 int receipts=0;bool accept=true;
 auto phase(){return state;}
 const char* boot_id(){return "abababababababababababababababab";}
 const char* command_id(){return "route-test";}
 const char* reason(){return "TEST_ONLY";}
 unsigned sequence(){return 0;}unsigned writes(){return 0;}
 const char* record(){return "{\"test\":true}";}
 auto enable_delivery(){return rocell_diag::ShoulderEnableDelivery::NotAttempted;}
 bool receipt(rocell_diag::ShoulderReceiptView r,uint64_t now){
   assert(r.size==124&&now==1000);++receipts;
   if(!accept){state=rocell_diag::ShoulderPreloadPhase::Fault;return false;}
   state=rocell_diag::ShoulderPreloadPhase::Write;return true;
 }
};
struct Access {Session* session=nullptr;Session* operator()(){return session;}};
struct Web {
 std::map<std::string,std::function<void()>> routes;std::map<std::string,int> methods;
 int parameters=0,status=0;std::string body,name="plain",response;
 void on(const char* p,int m,std::function<void()> f){routes[p]=f;methods[p]=m;}
 int args(){return parameters;}std::string argName(int){return name;}std::string arg(const char*){return body;}
 void sendHeader(const char*,const char*){}void send(int n,const char*,const char* p){status=n;response=p;}
};
int main(){
 Clock clock;Access access;Web web;Session session;
 rocell_diag::ShoulderSessionRoutes<Access,Clock,Web> routes(access,clock,web);
 routes.register_routes();routes.register_routes();assert(web.routes.size()==3);
 auto status=web.routes.at("/rocell/shoulder-session/status");
 auto record=web.routes.at("/rocell/shoulder-session/record");
 auto receipt=web.routes.at("/rocell/shoulder-session/receipt");
 status();assert(web.status==409);record();assert(web.status==409);
 access.session=&session;status();assert(web.status==200&&session.receipts==0);
 JsonDocument doc;assert(!deserializeJson(doc,web.response));assert(doc["state"]=="WAITING_EXPORT");
 assert(!doc["lift_authorized"].as<bool>());record();assert(web.status==200&&session.receipts==0);
 receipt();assert(web.status==400&&session.receipts==0);
 web.parameters=1;web.body=std::string(248,'0');web.name="query";receipt();assert(web.status==400);
 web.name="plain";web.body[0]='X';receipt();assert(web.status==400&&session.receipts==0);
 web.body[0]='0';receipt();assert(web.status==200&&session.receipts==1);
 receipt();assert(web.status==409&&session.receipts==1);
 session.state=rocell_diag::ShoulderPreloadPhase::Waiting;session.accept=false;
 receipt();assert(web.status==409&&session.receipts==2);
 web.parameters=0;record();assert(web.status==200); // fault evidence remains readable
 std::cout<<"SHOULDER_ROUTES_OFFLINE_PASSED\n";
}

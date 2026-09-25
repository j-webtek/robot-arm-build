#include <cassert>
#include <map>
#include <functional>
#include <string>
#include "baseline_only_owner.h"
const int HTTP_POST=1,HTTP_GET=0;
#include "baseline_only_routes.h"
struct Text {
 std::string data;size_t length()const{return data.size();}const char* c_str()const{return data.c_str();}
};
struct Server {
 std::map<int,std::function<void()>> routes;std::string input,output;int code=0;
 void on(const char*,int method,std::function<void()> fn){routes[method]=fn;}
 Text arg(const char*){return {input};}
 void sendHeader(const char*,const char*){}
 void send(int status,const char*,const char* body){code=status;output=body;}
};
struct Clock {uint64_t tick=100;uint64_t now_us(){return ++tick;}};
struct ReadOnlyBus {
  int End=0,Error=0,reads=0;bool fail=false;
  int Read(uint8_t,uint8_t,uint8_t* bytes,uint8_t width){
    ++reads;if(fail)return 0;bytes[0]=0x20;bytes[1]=0x08;return width;
  }
};
int main(){
  using namespace rocell_diag;
  for(bool failed:{false,true}){
    ReadOnlyBus bus;bus.fail=failed;Clock clock;DiagnosticSessionClaim claim;
    BaselineOnlyOwner<ReadOnlyBus,Clock> owner(bus,clock,claim,"boot");
    owner.poll();assert(bus.reads==0);
    assert(!owner.request("wrong","scan")&&!owner.request("boot","bad/id"));
    assert(claim.state()==DiagnosticClaim::Unclaimed);
    assert(owner.request("boot","scan")&&bus.reads==0);
    assert(!claim.claim(DiagnosticClaim::Motion));
    assert(!owner.request("boot","scan"));
    owner.poll();assert(bus.reads==(failed?2:14));
    assert(owner.state()==(failed?BaselineState::Fault:BaselineState::Captured));
    assert(owner.record()[0]);const int before=bus.reads;
    owner.poll();assert(bus.reads==before&&!owner.request("boot","new-scan"));
    assert(!claim.claim(DiagnosticClaim::Motion));
  }
  {ReadOnlyBus bus;Clock clock;DiagnosticSessionClaim claim;
   assert(claim.claim(DiagnosticClaim::Motion));
   BaselineOnlyOwner<ReadOnlyBus,Clock> owner(bus,clock,claim,"boot");
   assert(!owner.request("boot","scan"));owner.poll();assert(bus.reads==0);}
  {ReadOnlyBus bus;Clock clock;DiagnosticSessionClaim claim;Server server;
   BaselineOnlyOwner<ReadOnlyBus,Clock> owner(bus,clock,claim,"boot");
   register_baseline_only_routes(server,owner);
   server.routes.at(HTTP_GET)();assert(server.code==409&&bus.reads==0);
   for(const auto& input:{"{}","{\"boot_id\":\"boot\",\"scan_id\":\"scan\",\"extra\":1}",
                         "{\"boot_id\":\"boot\",\"boot_id\":\"boot\",\"scan_id\":\"scan\"}"}){
     server.input=input;server.routes.at(HTTP_POST)();assert(server.code==400&&bus.reads==0);}
   server.input="{\"boot_id\":\"boot\",\"scan_id\":\"scan\"}";
   server.routes.at(HTTP_POST)();assert(server.code==202&&bus.reads==0);
   server.routes.at(HTTP_POST)();assert(server.code==409&&bus.reads==0);
   owner.poll();assert(bus.reads==14);
   server.routes.at(HTTP_GET)();assert(server.code==200&&bus.reads==14);
   server.routes.at(HTTP_POST)();assert(server.code==409&&bus.reads==14);
   assert(!claim.claim(DiagnosticClaim::Motion));}
}

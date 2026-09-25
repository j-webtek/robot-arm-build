#include <cassert>
#include <fstream>
#include <string>
#include <map>
#include <functional>
#include <new>
bool fail_prepare_allocation=false;
void* operator new(size_t size,const std::nothrow_t&) noexcept {
  if(fail_prepare_allocation)return nullptr;
  try{return ::operator new(size);}catch(...){return nullptr;}
}
void operator delete(void* ptr,const std::nothrow_t&) noexcept {::operator delete(ptr);}
#include "controller_hold_config.h"
#include "controller_diagnostic_config.h"
#include "diagnostic_session.h"
#include "held_pair_network_lifecycle.h"
constexpr int HTTP_GET=0,HTTP_POST=1;
int mode=0,opens=0,initializations=0,rocellHoldCrypto=0,rocellPairEntropy=0;
struct ReadOnlyBus {int End=0,Error=0;
  int Read(uint8_t,uint8_t,uint8_t*,uint8_t){assert(false);return 0;}} st;
struct Clock {uint64_t now_us(){assert(false);return 0;}} rocellConfiguredClock;
bool rocellHoldConfigured=true;
#ifdef ROCELL_POSE_OBSERVATION
#include "pose_observation_reservation.h"
bool rocellDiagnosticOwned=false,rocellHoldChallengeAttempted=false,rocellRecoveryReserved=false;
#endif
char rocellHoldPolicy[2048]={},rocellDiagnosticInstance[33]="11111111111111111111111111111111";
bool rocellHoldHealthy(void*){return true;}
struct Hold {bool exclusive_work(){return false;}
  rocell_diag::SessionState state(){return rocell_diag::SessionState::Captured;}} rocellConfiguredRuntime;
struct File {
  std::string data;bool valid=true,short_read=false;
  explicit operator bool()const{return valid;}
  size_t size(){return data.size();}
  size_t read(uint8_t* out,size_t n){if(short_read&&n)--n;memcpy(out,data.data(),n);return n;}
  void close(){}
};
struct Filesystem {
  File open(const char* path,const char* access){
    ++opens;assert(!strcmp(access,"r"));
    if(!strcmp(path,"/rocell-pair.json")){
      File f{"{\"forward_command_id\":\"forward\",\"offset_counts\":6,\"return_command_id\":\"return\",\"schema\":\"rocell.controller_pair.v1\",\"tolerance_counts\":2}"};
      if(mode==1)f.valid=false;
      if(mode==2)f.data="{}";
      if(mode==3)f.data.insert(f.data.find("\"offset_counts\""),"\"offset_counts\":7,");
      if(mode==4)f.short_read=true;
      if(mode==7)f.data.replace(f.data.find("\"return\""),8,"\"forward\"");
      return f;
    }
    assert(!strcmp(path,"/rocell-hold.key"));File f{std::string(32,'k')};
    if(mode==5)f.valid=false;if(mode==6)f.short_read=true;return f;
  }
} LittleFS;
struct Pair {
  rocell_diag::PairNetworkPhase phase(){return rocell_diag::PairNetworkPhase::New;}
  template<class... Args>bool initialize_from_hold(Args&&...){++initializations;return true;}
  bool issue_initial(char* out,size_t n){snprintf(out,n,"{}");return true;}
  bool issue_return(char*,size_t){return false;}
  bool exclusive_work(){return false;}
  bool status_json(char*,size_t){return false;}
  bool record_json(size_t,char*,size_t){return false;}
  size_t record_count(){return 0;}
  void export_failed(){}
} rocellPairRuntime;
using RocellPairRuntime=Pair;
struct WebServer {
  std::map<std::string,std::function<void()>> routes;int code=0;std::string body;
  void on(const char* p,int,std::function<void()> f){routes[p]=f;}
  void sendHeader(const char*,const char*){}
  void send(int c,const char*,const char* b){code=c;body=b;}
  std::string arg(const char*){return "0";}
  int args(){return 0;}
} server;
struct Metrics {unsigned getFreeHeap(){return 120000;}unsigned getMinFreeHeap(){return 110000;}
  unsigned getMaxAllocHeap(){return 100000;}} ESP;
void registerHoldDiagnosticRoutes(){}
#include "configured_pair_board_routes.h"
int main(int argc,char** argv){
  assert(argc==3);mode=atoi(argv[2]);std::ifstream input(argv[1],std::ios::binary);
  std::string config((std::istreambuf_iterator<char>(input)),{});assert(config.size()<sizeof(rocellHoldPolicy));
  memcpy(rocellHoldPolicy,config.data(),config.size());
  for(int offset:{-17,-16,-6,-4,0,4,6,16,17}){
    char text[512];snprintf(text,sizeof(text),
      "{\"forward_command_id\":\"forward\",\"offset_counts\":%d,\"return_command_id\":\"return\",\"schema\":\"rocell.controller_pair.v1\",\"tolerance_counts\":2}",offset);
    rocell_diag::ControllerPairConfigParser parser;
    assert(parser.parse(text,strlen(text))==(offset>=-16&&offset<=16&&(offset<-4||offset>4)));
    assert(!parser.parse(text,strlen(text)));
  }
  if(mode==8)rocellHoldPolicy[0]='x';if(mode==9)rocellHoldConfigured=false;
  registerDiagnosticRoutes();assert(opens==0&&initializations==0&&server.routes.size()==9);
  server.routes.at("/rocell/held-pair/capabilities")();assert(server.code==200&&opens==0&&initializations==0);
  JsonDocument metrics;assert(!deserializeJson(metrics,server.body));
  assert(metrics["free_internal_heap_bytes"]==120000&&metrics["largest_internal_block_bytes"]==100000);
  assert(metrics["stack_measured"]==false);
  fail_prepare_allocation=mode==10;
  server.routes.at("/rocell/held-pair/prepare")();
  assert(server.code==(mode==0?200:503));assert(initializations==(mode==0?1:0));
  if(mode==2||mode==3||mode==4||mode==7)assert(opens==1); // No key access after bad settings.
  if(mode==8||mode==9||mode==10)assert(opens==0);
  int prior=opens;server.routes.at("/rocell/held-pair/prepare")();assert(server.code==409&&opens==prior);
}

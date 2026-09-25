#include <cassert>
#include <fstream>
#include <string>
#include <map>
#include <functional>
#include "controller_hold_config.h"
#include "controller_diagnostic_config.h"
constexpr int HTTP_GET=0,HTTP_POST=1;
int mode=0,opens=0,initializations=0,st=0,rocellHoldCrypto=0;
bool rocellRecoveryReserved=false,rocellHoldChallengeAttempted=false,rocellHoldConfigured=false,rocellDiagnosticOwned=false;
char rocellDiagnosticInstance[33]="11111111111111111111111111111111";
std::string source;
bool rocellHoldHealthy(void*){return mode!=9;}
struct Clock {uint64_t now_us(){return 1000;}} rocellConfiguredClock;
void esp_fill_random(uint8_t* out,size_t n){memset(out,0x22,n);}
namespace rocell_diag {enum class PairNetworkPhase {New,AwaitReturn};}
struct Pair {rocell_diag::PairNetworkPhase phase(){return mode==8?
  rocell_diag::PairNetworkPhase::AwaitReturn:rocell_diag::PairNetworkPhase::New;}} rocellPairRuntime;
struct File {
  std::string data;bool valid=true,short_read=false;
  explicit operator bool()const{return valid;}
  size_t size(){return data.size();}
  size_t read(uint8_t* out,size_t n){if(short_read&&n)--n;memcpy(out,data.data(),n);return n;}
  void close(){}
};
struct FS {
  File open(const char* path,const char* access){
    assert(rocellRecoveryReserved&&rocellDiagnosticOwned&&!strcmp(access,"r"));++opens;
    if(!strcmp(path,"/rocell-hold.json")){
      File f{source};if(mode==1)f.valid=false;if(mode==2)f.data="{}";if(mode==3)f.short_read=true;return f;
    }
    assert(!strcmp(path,"/rocell-hold.key"));File f{std::string(32,'k')};
    if(mode==4)f.valid=false;if(mode==5)f.short_read=true;return f;
  }
} LittleFS;
struct Recovery {
  int faults=0;
  bool initialize(int&,Clock&,int&,const uint8_t (&key)[32],const uint8_t (&boot)[16],
      const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires,uint16_t port,
      const rocell_diag::HoldInitializationPolicy& p,const char* command,bool(*)(void*),void*){
    ++initializations;assert(key[0]=='k'&&boot[0]==0x11&&nonce[0]==0x22);
    assert(issued==1000&&expires==10001000&&port==8081&&!p.permit_explicit_enable);
    assert(p.drift==2&&p.minimum[3]==2893&&p.maximum[3]==2909);
#ifdef ROCELL_OBSERVED_POSE_RECOVERY
    JsonDocument configured;assert(!deserializeJson(configured,source));
    const bool observed=!strcmp(configured["command_id"].as<const char*>(),"observed-pose-elbow-hold-v1");
    assert(!strcmp(command,observed?"observed-pose-six-count-recovery-v1":"r18-six-count-recovery"));
#else
    assert(!strcmp(command,"r15-supported-recovery"));
#endif
    return mode!=6;
  }
  void interference(){++faults;}
  void export_failed(){++faults;}
  bool exclusive_work(){return false;}
  bool status_json(char*,size_t){return false;}
  bool record_json(size_t,char*,size_t){return false;}
  size_t size(){return 0;}
} rocellRecoveryRuntime;
using RocellRecoveryRuntime=Recovery;
struct WebServer {
  std::map<std::string,std::function<void()>> routes;int code=0;std::string body;
  void on(const char* p,int,std::function<void()> f){routes[p]=f;}
  int args(){return 0;}
  std::string arg(const char*){return "0";}
  void sendHeader(const char*,const char*){}
  void send(int c,const char*,const char* b){code=c;body=b;}
} server;
#include "configured_recovery_board_routes.h"
int main(int argc,char** argv){
  assert(argc==3);mode=atoi(argv[2]);std::ifstream input(argv[1],std::ios::binary);
  source=std::string((std::istreambuf_iterator<char>(input)),{});
  if(mode==7)rocellHoldChallengeAttempted=true;
  if(mode==10)rocellHoldConfigured=true;
  if(mode==11){JsonDocument doc;assert(!deserializeJson(doc,source));doc["hold_policy"]["drift"]=3;source.clear();serializeJson(doc,source);}
  if(mode==12){JsonDocument doc;assert(!deserializeJson(doc,source));doc["command_id"]="unknown-hold";source.clear();serializeJson(doc,source);}
  if(mode==13){JsonDocument doc;assert(!deserializeJson(doc,source));doc["hold_policy"]["joints"][1][0]=2484;source.clear();serializeJson(doc,source);}
  rocellRecoveryRoutes.register_routes();assert(opens==0&&initializations==0);
  auto prepare=server.routes.at("/rocell/recovery/prepare");prepare();
  assert(server.code==(mode==0?200:503));
  assert(initializations==((mode==0||mode==6)?1:0));
  if(mode==7||mode==8||mode==9||mode==10)assert(opens==0&&!rocellRecoveryReserved);
  else assert(rocellRecoveryReserved);
  int prior=opens;prepare();assert(server.code==409&&opens==prior);
}

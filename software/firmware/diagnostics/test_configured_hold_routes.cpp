#include <cassert>
#include <cstring>
#include <string>
#include <map>
#include <functional>
#include "controller_diagnostic_config.h"
int mode=0,opens=0;
using String=std::string;
struct File {
  std::string data;bool valid=true,short_read=false;
  explicit operator bool()const{return valid;}
  size_t size()const{return data.size();}
  size_t read(uint8_t* out,size_t n){if(short_read)--n;memcpy(out,data.data(),n);return n;}
  void close(){}
};
struct Filesystem {
  File open(const char* path,const char* access){
    ++opens;assert(!strcmp(access,"r"));
    if(!strcmp(path,"/rocell-hold.json")){
      File f{"policy",mode!=1,mode==4};
      if(mode==2)f.data.clear();if(mode==3)f.data=std::string(2049,'x');return f;
    }
    assert(!strcmp(path,"/rocell-hold.key"));
    File f;for(int i=0;i<32;++i)f.data.push_back(char(31-i));
    if(mode==5)f.data.resize(31);if(mode==7)f.data=std::string(32,0);return f;
  }
} LittleFS;
struct Clock {uint64_t now_us(){return 1000;}} rocellConfiguredClock;
int st=0,rocellHoldCrypto=0;
bool rocellDiagnosticOwned=false;
char rocellDiagnosticInstance[33]={};
bool rocellHoldHealthy(void*){return true;}
unsigned long esp_random(){return 0x11111111;}
void esp_fill_random(void* p,size_t n){memset(p,0x22,n);}
struct Runtime {
  int calls=0,failures=0;
  bool initialize_config(int&,Clock&,int&,const uint8_t (&key)[32],const uint8_t (&boot)[16],
      const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires,const char* bytes,size_t n,
      bool (*healthy)(void*),void* context){
    ++calls;assert(key[0]==31&&boot[0]==0x11&&nonce[0]==0x22&&healthy(context));
    assert(issued==1000&&expires==10001000&&std::string(bytes,n)=="policy");return mode!=6;
  }
  void export_failed(){++failures;}
  bool status_json(char* out,size_t n){snprintf(out,n,"{\"configured\":true}");return true;}
  const void* get(size_t i){return i==0&&calls?this:nullptr;}
  bool record_json(size_t,char* out,size_t n){snprintf(out,n,"{\"record\":true}");return true;}
} rocellConfiguredRuntime;
const int HTTP_GET=0;
struct Server {
  std::map<std::string,std::function<void()>> routes;std::string body,query,cache;int code=0;
  void on(const char* p,int method,std::function<void()> fn){assert(method==HTTP_GET);routes[p]=fn;}
  void sendHeader(const char* n,const char* v){assert(!strcmp(n,"Cache-Control"));cache=v;}
  void send(int c,const char*,const char* b){code=c;body=b;}
  String arg(const char* n){assert(!strcmp(n,"index"));return query;}
} server;
#define ROCELL_RECOVERY_DIAGNOSTIC_OWNER 1
bool rocellRecoveryReserved=false;
#include "configured_hold_routes.h"
int main(int argc,char** argv){
  assert(argc==2);mode=atoi(argv[1]);registerDiagnosticRoutes();
  assert(opens==0&&server.routes.size()==3);
  auto status=server.routes.at("/rocell/diagnostics/status");status();
  assert(server.code==200&&server.body.find("IDLE")!=std::string::npos&&opens==0);
  if(mode==8){
    rocellRecoveryReserved=true;server.routes.at("/rocell/diagnostics/challenge")();
    assert(server.code==503&&opens==0&&rocellConfiguredRuntime.calls==0&&!rocellHoldChallengeAttempted);
    return 0;
  }
  auto challenge=server.routes.at("/rocell/diagnostics/challenge");challenge();
  assert(server.code==(mode?503:200)&&rocellDiagnosticOwned);
  const int before=opens,calls=rocellConfiguredRuntime.calls;const auto body=server.body;
  challenge();assert(opens==before&&calls==rocellConfiguredRuntime.calls&&body==server.body);
  status();assert(server.body.find(mode?"FAULT":"configured")!=std::string::npos);
  auto record=server.routes.at("/rocell/diagnostics/record");
  for(const auto* q:{"","-1","a","123"," 0"}){server.query=q;record();assert(server.code==400);}
  server.query="12";record();assert(server.code==404);
  assert(opens==before&&calls==rocellConfiguredRuntime.calls&&server.cache=="no-store");
}

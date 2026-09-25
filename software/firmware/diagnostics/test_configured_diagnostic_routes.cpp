#include <cassert>
#include <fstream>
#include <iterator>
#include <string>
#include <map>
#include <functional>
#include "controller_diagnostic_config.h"
int mode=0,opens=0;std::string policy_data;
struct File {
  std::string data;bool valid=true;bool short_read=false;
  explicit operator bool() const{return valid;}
  size_t size() const{return data.size();}
  size_t read(uint8_t* output,size_t length){
    const size_t n=short_read?length-1:length;memcpy(output,data.data(),n);return n;
  }
  void close(){}
};
struct Filesystem {
  File open(const char* path,const char* access){
    assert(!strcmp(access,"r"));++opens;
    if(!strcmp(path,"/rocell-diagnostics.json")){
      File file{policy_data,mode!=1,mode==4};
      if(mode==2)file.data.clear();if(mode==3)file.data=std::string(4097,'x');return file;
    }
    assert(!strcmp(path,"/rocell-diagnostics.key"));
    File file;for(int i=0;i<32;++i)file.data.push_back(static_cast<char>(31-i));
    if(mode==5)file.data.resize(31);return file;
  }
} LittleFS;
struct Runtime {
  int calls=0,failures=0;
  void configuration_failed(){++failures;}
  void export_failed(){++failures;}
  bool initialize(int&,int&,const char* bytes,size_t length,const char* conversion,
      const rocell_diag::DiagnosticKeyMaterial& material,const uint8_t (&boot)[16],
      const uint8_t (&nonce)[32],bool (*fault)(void*),void* context){
    ++calls;uint8_t key[32];assert(material.copy_to(key));
    assert(boot[0]==0x11 && nonce[0]==0x22 && !fault(context));
    rocell_diag::ControllerDiagnosticConfigParser parser;
    return parser.parse(bytes,length,conversion) && mode!=6;
  }
  uint64_t issued_us(){return 1001;}uint64_t expires_us(){return 11001;}
} rocellConfiguredRuntime;
int st=0,rocellConfiguredClock=0;
bool rocellDiagnosticOwned=false;
char rocellDiagnosticInstance[33]="11111111111111111111111111111111";
bool rocellConfiguredFault(void*){return false;}
void esp_fill_random(void* bytes,size_t count){memset(bytes,0x22,count);}
const int HTTP_GET=0;
struct Server {
  std::map<std::string,std::function<void()>> routes;std::string body,cache;int code=0;
  void on(const char* path,int method,std::function<void()> handler){assert(method==HTTP_GET);routes[path]=handler;}
  void sendHeader(const char* name,const char* value){assert(!strcmp(name,"Cache-Control"));cache=value;}
  void send(int status,const char*,const char* value){code=status;body=value;}
} server;
#ifdef ROCELL_TEST_BASELINE_COMPOSITION
#include "diagnostic_session_claim.h"
rocell_diag::DiagnosticSessionClaim rocellSessionClaim;
#include "../../.firmware-tools/configured-diagnostic-candidate-r3/RoArm-M3_example/configured_diagnostic_routes.h"
#else
#include "configured_diagnostic_routes.h"
#endif
int main(int argc,char** argv){
  assert(argc==3);mode=atoi(argv[1]);std::ifstream source(argv[2],std::ios::binary);
  policy_data.assign(std::istreambuf_iterator<char>(source),{});
#ifdef ROCELL_TEST_BASELINE_COMPOSITION
  if(mode==8)assert(rocellSessionClaim.claim(rocell_diag::DiagnosticClaim::Baseline));
#endif
  registerConfiguredChallengeRoute();assert(opens==0 && server.routes.size()==1);
  auto invoke=server.routes.at("/rocell/diagnostics/challenge");invoke();
#ifdef ROCELL_TEST_BASELINE_COMPOSITION
  if(mode==8){
    assert(server.code==503&&opens==0&&rocellConfiguredRuntime.calls==0);
    assert(!rocellChallengeAttempted&&!rocellDiagnosticOwned);
    invoke();assert(opens==0&&rocellConfiguredRuntime.calls==0);return 0;
  }
  assert(rocellSessionClaim.state()==rocell_diag::DiagnosticClaim::Motion);
  assert(!rocellSessionClaim.claim(rocell_diag::DiagnosticClaim::Baseline));
#endif
  assert(rocellDiagnosticOwned && rocellChallengeAttempted);
  assert(server.code==(mode==0?200:503) && server.cache=="no-store");
  const int before=opens,calls=rocellConfiguredRuntime.calls;const auto body=server.body;
  invoke();assert(opens==before && rocellConfiguredRuntime.calls==calls && server.body==body);
  assert(server.body.find("key")==std::string::npos);
  puts(server.body.c_str());
}

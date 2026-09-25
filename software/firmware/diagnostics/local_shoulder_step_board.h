// Alternate board composition, opt-in only. Existing diagnostics own the common
// reservation flags, clock, health checks and server. Startup performs no I/O.
#pragma once
#include "local_shoulder_step_routes.h"
#include "shoulder_fault_settling_routes.h"
#include <memory>
#include <new>
using RocellLocalSession=rocell_diag::LocalShoulderStepSession<rocell_diag::Esp32StartCrypto>;
using RocellLocalSettling=rocell_diag::ShoulderFaultSettlingSession<rocell_diag::Esp32StartCrypto,RocellLocalSession>;
std::unique_ptr<RocellLocalSession> rocellLocalSession;
std::unique_ptr<RocellLocalSettling> rocellLocalSettling;
char rocellLocalChallenge[512]={};
constexpr size_t rocellLocalHeapReserve=32768;
bool rocellLocalMemoryFits(size_t free_bytes,size_t largest_block){
  const size_t total=sizeof(RocellLocalSession)+sizeof(RocellLocalSettling);
  return free_bytes>=total+rocellLocalHeapReserve&&
    largest_block>=(sizeof(RocellLocalSession)>sizeof(RocellLocalSettling)?sizeof(RocellLocalSession):sizeof(RocellLocalSettling));
}
bool rocellPrepareLocalStep(){
  if(rocellShoulderReserved||rocellDiagnosticOwned||rocellPoseReserved||rocellHoldChallengeAttempted||
      rocellHoldConfigured||rocellRecoveryReserved||rocellPairRuntime.phase()!=rocell_diag::PairNetworkPhase::New||
      !rocellHoldHealthy(nullptr)||!rocellConfigurationBusInactive(nullptr)||
      !rocellLocalMemoryFits(ESP.getFreeHeap(),ESP.getMaxAllocHeap()))return false;
  rocellShoulderReserved=true;rocellDiagnosticOwned=true; // Never refund partial setup.
  File file=LittleFS.open("/rocell-hold.key","r");rocell_diag::DiagnosticKeyMaterial material;
  if(!material.load(file)){file.close();return false;}file.close();
  uint8_t key[32]={},boot[16]={},nonce[32]={};
  if(!material.copy_to(key)){material.clear();return false;}material.clear();
  auto nibble=[](char c)->uint8_t{return c>='a'?c-'a'+10:c-'0';};
  for(unsigned i=0;i<16;++i)boot[i]=(nibble(rocellDiagnosticInstance[2*i])<<4)|nibble(rocellDiagnosticInstance[2*i+1]);
  esp_fill_random(nonce,32);const auto issued=rocellConfiguredClock.now_us(),expires=issued+30000000;
  rocellLocalSession.reset(new(std::nothrow) RocellLocalSession(rocellHoldCrypto,key,boot,nonce,issued,expires,"local-step-1"));
  if(rocellLocalSession)rocellLocalSettling.reset(new(std::nothrow) RocellLocalSettling(rocellHoldCrypto,*rocellLocalSession,key,boot));
  volatile uint8_t* wipe=key;for(unsigned i=0;i<32;++i)wipe[i]=0;
  if(!rocellLocalSession||!rocellLocalSettling||ESP.getFreeHeap()<rocellLocalHeapReserve){
    rocellLocalSettling.reset();rocellLocalSession.reset();return false;
  }
  char hex[65]={};const char* digits="0123456789abcdef";
  for(unsigned i=0;i<32;++i){hex[i*2]=digits[nonce[i]>>4];hex[i*2+1]=digits[nonce[i]&15];}
  int n=snprintf(rocellLocalChallenge,sizeof(rocellLocalChallenge),
    "{\"schema\":\"rocell.start_challenge.v1\",\"boot_id\":\"%s\",\"nonce\":\"%s\",\"issued_us\":%llu,\"expires_us\":%llu}",
    rocellDiagnosticInstance,hex,(unsigned long long)issued,(unsigned long long)expires);
  if(n<=0||size_t(n)>=sizeof(rocellLocalChallenge)){rocellLocalSettling.reset();rocellLocalSession.reset();return false;}
  return true;
}
struct RocellLocalAccess{RocellLocalSession* operator()(){return rocellLocalSession.get();}} rocellLocalAccess;
struct RocellLocalSettlingAccess{RocellLocalSettling* operator()(){
  return rocellLocalSession&&rocellLocalSession->local_phase()==rocell_diag::LocalStepPhase::Fault?rocellLocalSettling.get():nullptr;
}} rocellLocalSettlingAccess;
rocell_diag::LocalShoulderStepRoutes<RocellLocalAccess,RocellConfiguredClock,WebServer>
  rocellLocalRoutes(rocellLocalAccess,rocellConfiguredClock,server);
rocell_diag::ShoulderFaultSettlingRoutes<RocellLocalSettlingAccess,RocellConfiguredClock,WebServer>
  rocellLocalSettlingRoutes(rocellLocalSettlingAccess,rocellConfiguredClock,server);
void registerShoulderSessionRoutes(){
  rocellLocalRoutes.register_routes();rocellLocalSettlingRoutes.register_routes();
  server.on("/rocell/local-step/prepare",HTTP_POST,[](){
    server.sendHeader("Cache-Control","no-store");
    if(server.args()){server.send(400,"application/json","{}");return;}
    bool ok=rocellPrepareLocalStep();server.send(ok?200:409,"application/json",ok?rocellLocalChallenge:"{\"error\":\"LOCAL_PREPARE_REJECTED\"}");
  });
}
void pollShoulderSession(){
  auto admission=[](){return rocellShoulderReserved&&rocellHoldHealthy(nullptr);};
  if(rocellLocalSession)rocellLocalSession->advance(st,rocellConfiguredClock,admission);
  if(auto* capture=rocellLocalSettlingAccess())capture->advance(st,rocellConfiguredClock,admission);
  server.handleClient();
}

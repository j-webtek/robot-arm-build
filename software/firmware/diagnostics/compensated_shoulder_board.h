// Alternate board composition, opt-in only. Existing diagnostics own the common
// reservation flags, clock, health checks and server. Startup performs no I/O.
#pragma once
#include "compensated_shoulder_routes.h"
#include "shoulder_fault_settling_routes.h"
#include <memory>
#include <new>
using RocellCompensatedSession=rocell_diag::CompensatedShoulderStepSession<rocell_diag::Esp32StartCrypto>;
using RocellCompensatedSettling=rocell_diag::ShoulderFaultSettlingSession<rocell_diag::Esp32StartCrypto,RocellCompensatedSession>;
std::unique_ptr<RocellCompensatedSession> rocellCompensatedSession;
std::unique_ptr<RocellCompensatedSettling> rocellCompensatedSettling;
char rocellCompensatedChallenge[512]={};
constexpr size_t rocellCompensatedHeapReserve=32768;
bool rocellCompensatedMemoryFits(size_t free_bytes,size_t largest_block){
  const size_t total=sizeof(RocellCompensatedSession)+sizeof(RocellCompensatedSettling);
  return free_bytes>=total+rocellCompensatedHeapReserve&&
    largest_block>=(sizeof(RocellCompensatedSession)>sizeof(RocellCompensatedSettling)?sizeof(RocellCompensatedSession):sizeof(RocellCompensatedSettling));
}
bool rocellPrepareCompensatedStep(){
  if(rocellShoulderReserved||rocellDiagnosticOwned||rocellPoseReserved||rocellHoldChallengeAttempted||
      rocellHoldConfigured||rocellRecoveryReserved||rocellPairRuntime.phase()!=rocell_diag::PairNetworkPhase::New||
      !rocellHoldHealthy(nullptr)||!rocellConfigurationBusInactive(nullptr)||
      !rocellCompensatedMemoryFits(ESP.getFreeHeap(),ESP.getMaxAllocHeap()))return false;
  rocellShoulderReserved=true;rocellDiagnosticOwned=true; // Never refund partial setup.
  File file=LittleFS.open("/rocell-hold.key","r");rocell_diag::DiagnosticKeyMaterial material;
  if(!material.load(file)){file.close();return false;}file.close();
  uint8_t key[32]={},boot[16]={},nonce[32]={};
  if(!material.copy_to(key)){material.clear();return false;}material.clear();
  auto nibble=[](char c)->uint8_t{return c>='a'?c-'a'+10:c-'0';};
  for(unsigned i=0;i<16;++i)boot[i]=(nibble(rocellDiagnosticInstance[2*i])<<4)|nibble(rocellDiagnosticInstance[2*i+1]);
  esp_fill_random(nonce,32);const auto issued=rocellConfiguredClock.now_us(),expires=issued+30000000;
  rocellCompensatedSession.reset(new(std::nothrow) RocellCompensatedSession(rocellHoldCrypto,key,boot,nonce,issued,expires,"compensated-step-1"));
  if(rocellCompensatedSession)rocellCompensatedSettling.reset(new(std::nothrow) RocellCompensatedSettling(rocellHoldCrypto,*rocellCompensatedSession,key,boot));
  volatile uint8_t* wipe=key;for(unsigned i=0;i<32;++i)wipe[i]=0;
  if(!rocellCompensatedSession||!rocellCompensatedSettling||ESP.getFreeHeap()<rocellCompensatedHeapReserve){
    rocellCompensatedSettling.reset();rocellCompensatedSession.reset();return false;
  }
  char hex[65]={};const char* digits="0123456789abcdef";
  for(unsigned i=0;i<32;++i){hex[i*2]=digits[nonce[i]>>4];hex[i*2+1]=digits[nonce[i]&15];}
  int n=snprintf(rocellCompensatedChallenge,sizeof(rocellCompensatedChallenge),
    "{\"schema\":\"rocell.start_challenge.v1\",\"boot_id\":\"%s\",\"nonce\":\"%s\",\"issued_us\":%llu,\"expires_us\":%llu}",
    rocellDiagnosticInstance,hex,(unsigned long long)issued,(unsigned long long)expires);
  if(n<=0||size_t(n)>=sizeof(rocellCompensatedChallenge)){rocellCompensatedSettling.reset();rocellCompensatedSession.reset();return false;}
  return true;
}
struct RocellCompensatedAccess{RocellCompensatedSession* operator()(){return rocellCompensatedSession.get();}} rocellCompensatedAccess;
struct RocellCompensatedSettlingAccess{RocellCompensatedSettling* operator()(){
  return rocellCompensatedSession&&rocellCompensatedSession->local_phase()==rocell_diag::CompensatedStepPhase::Fault?rocellCompensatedSettling.get():nullptr;
}} rocellCompensatedSettlingAccess;
rocell_diag::CompensatedShoulderStepRoutes<RocellCompensatedAccess,RocellConfiguredClock,WebServer>
  rocellCompensatedRoutes(rocellCompensatedAccess,rocellConfiguredClock,server);
rocell_diag::ShoulderFaultSettlingRoutes<RocellCompensatedSettlingAccess,RocellConfiguredClock,WebServer>
  rocellCompensatedSettlingRoutes(rocellCompensatedSettlingAccess,rocellConfiguredClock,server);
void registerShoulderSessionRoutes(){
  rocellCompensatedRoutes.register_routes();rocellCompensatedSettlingRoutes.register_routes();
  server.on("/rocell/compensated-step/prepare",HTTP_POST,[](){
    server.sendHeader("Cache-Control","no-store");
    if(server.args()){server.send(400,"application/json","{}");return;}
    bool ok=rocellPrepareCompensatedStep();server.send(ok?200:409,"application/json",ok?rocellCompensatedChallenge:"{\"error\":\"COMPENSATED_PREPARE_REJECTED\"}");
  });
}
void pollShoulderSession(){
  auto admission=[](){return rocellShoulderReserved&&rocellHoldHealthy(nullptr);};
  if(rocellCompensatedSession)rocellCompensatedSession->advance(st,rocellConfiguredClock,admission);
  if(auto* capture=rocellCompensatedSettlingAccess())capture->advance(st,rocellConfiguredClock,admission);
  server.handleClient();
}

// Included after existing diagnostic/pose declarations in the staged candidate.
// Explicit prepare reads the existing private key; never provisions settings.
#pragma once
#if defined(ROCELL_CHARACTERIZATION_SMOKE) && (defined(ROCELL_COMPENSATED_SHOULDER_STEP) || defined(ROCELL_LOCAL_SHOULDER_STEP))
#error Select only one shoulder owner
#endif
#if defined(ROCELL_COMPENSATED_SHOULDER_STEP) && defined(ROCELL_LOCAL_SHOULDER_STEP)
#error Select only one shoulder step contract
#endif
#if defined(ROCELL_CHARACTERIZATION_SMOKE)
#include "characterization_smoke_board.h"
#elif defined(ROCELL_COMPENSATED_SHOULDER_STEP)
#include "compensated_shoulder_board.h"
#elif defined(ROCELL_LOCAL_SHOULDER_STEP)
#include "local_shoulder_step_board.h"
#else
#include "shoulder_session_owner.h"
#include "shoulder_session_routes.h"
#if defined(ROCELL_FAULT_SETTLING_CAPTURE)
#include "shoulder_fault_settling_routes.h"
#endif
#include <memory>
#include <new>
using RocellShoulderOwner=rocell_diag::ShoulderSessionOwner<rocell_diag::Esp32StartCrypto>;
// A reviewed build must opt in; installed passive-only images remain unchanged.
#if defined(ROCELL_STABLE_CLEARANCE_RECOVERY)
constexpr auto rocellShoulderScope=rocell_diag::ShoulderSessionScope::StableClearanceRecovery;
constexpr const char* rocellShoulderCommand="shoulder-stable-clearance24-v1";
#elif defined(ROCELL_CLEARANCE_RECOVERY)
constexpr auto rocellShoulderScope=rocell_diag::ShoulderSessionScope::ClearanceRecovery;
constexpr const char* rocellShoulderCommand="shoulder-clearance24-v1";
#elif defined(ROCELL_SHOULDER_RISE)
constexpr auto rocellShoulderScope=rocell_diag::ShoulderSessionScope::ShoulderRise;
constexpr const char* rocellShoulderCommand="shoulder-rise12-v1";
#elif defined(ROCELL_POSE_PREPARATION)
constexpr auto rocellShoulderScope=rocell_diag::ShoulderSessionScope::PosePreparation;
constexpr const char* rocellShoulderCommand="pose-preparation-v1";
#elif defined(ROCELL_MIXED_TARGET_EXPERIMENT)
constexpr auto rocellShoulderScope=rocell_diag::ShoulderSessionScope::MixedTarget;
constexpr const char* rocellShoulderCommand="mixed-shoulder-target-v1";
#else
constexpr auto rocellShoulderScope=rocell_diag::ShoulderSessionScope::PairHold;
constexpr const char* rocellShoulderCommand="r23-shoulder-hold";
#endif
rocell_diag::ShoulderBusReservation rocellShoulderBus;
std::unique_ptr<RocellShoulderOwner> rocellShoulderOwner;
char rocellShoulderChallenge[512]={};
uint8_t rocellShoulderStartBytes[512]={};
bool rocellShoulderStartAttempted=false;
bool rocellShoulderAdmission(){
  // Physical admission belongs to the reviewed execution approval. This
  // controller check is health/ownership only; the session scans every joint
  // before preload/enable and does not infer board clearance from authentication.
  return rocellShoulderReserved&&rocellHoldHealthy(nullptr);
}
bool rocellPrepareShoulder(){
  if(rocellShoulderReserved||rocellDiagnosticOwned||rocellPoseReserved||
      rocellHoldChallengeAttempted||rocellHoldConfigured||rocellRecoveryReserved||
      rocellPairRuntime.phase()!=rocell_diag::PairNetworkPhase::New||
      !rocellHoldHealthy(nullptr)||!rocellConfigurationBusInactive(nullptr))return false;
  rocellShoulderReserved=true;rocellDiagnosticOwned=true;
  File file=LittleFS.open("/rocell-hold.key","r");
  rocell_diag::DiagnosticKeyMaterial material;
  if(!material.load(file)){file.close();return false;}file.close();
  uint8_t key[32]={},boot[16]={},nonce[32]={};
  if(!material.copy_to(key)){material.clear();return false;}material.clear();
  auto nibble=[](char c)->uint8_t{return c>='a'?c-'a'+10:c-'0';};
  for(unsigned i=0;i<16;++i)boot[i]=(nibble(rocellDiagnosticInstance[2*i])<<4)|nibble(rocellDiagnosticInstance[2*i+1]);
  esp_fill_random(nonce,sizeof(nonce));
  const auto issued=rocellConfiguredClock.now_us(),expires=issued+30000000;
  rocellShoulderOwner.reset(new(std::nothrow) RocellShoulderOwner(rocellHoldCrypto,
      rocellShoulderBus,key,boot,nonce,issued,expires,rocellShoulderCommand,rocellShoulderScope
#if defined(ROCELL_FAULT_SETTLING_CAPTURE)
      ,true
#endif
      ));
  volatile uint8_t* wipe=key;for(unsigned i=0;i<32;++i)wipe[i]=0;
  if(!rocellShoulderOwner)return false;
  char hex[65]={};const char* digits="0123456789abcdef";
  for(unsigned i=0;i<32;++i){hex[2*i]=digits[nonce[i]>>4];hex[2*i+1]=digits[nonce[i]&15];}
  int n=snprintf(rocellShoulderChallenge,sizeof(rocellShoulderChallenge),
    "{\"schema\":\"rocell.start_challenge.v1\",\"boot_id\":\"%s\",\"nonce\":\"%s\",\"issued_us\":%llu,\"expires_us\":%llu}",
    rocellDiagnosticInstance,hex,(unsigned long long)issued,(unsigned long long)expires);
  return n>0&&size_t(n)<sizeof(rocellShoulderChallenge);
}
struct RocellShoulderAccess{
  RocellShoulderOwner::Session* operator()(){return rocellShoulderOwner?rocellShoulderOwner->session():nullptr;}
} rocellShoulderAccess;
rocell_diag::ShoulderSessionRoutes<RocellShoulderAccess,RocellConfiguredClock,WebServer>
  rocellShoulderRoutes(rocellShoulderAccess,rocellConfiguredClock,server);
#if defined(ROCELL_FAULT_SETTLING_CAPTURE)
struct RocellSettlingAccess{
  RocellShoulderOwner::Settling* operator()(){
    return rocellShoulderOwner?rocellShoulderOwner->settling():nullptr;
  }
} rocellSettlingAccess;
rocell_diag::ShoulderFaultSettlingRoutes<RocellSettlingAccess,RocellConfiguredClock,WebServer>
  rocellSettlingRoutes(rocellSettlingAccess,rocellConfiguredClock,server);
#endif
void registerShoulderSessionRoutes(){
  rocellShoulderRoutes.register_routes();
#if defined(ROCELL_FAULT_SETTLING_CAPTURE)
  rocellSettlingRoutes.register_routes();
#endif
  server.on("/rocell/shoulder-session/prepare",HTTP_POST,[](){
    server.sendHeader("Cache-Control","no-store");
    if(server.args()!=0){server.send(400,"application/json","{\"error\":\"NO_PARAMETERS_ALLOWED\"}");return;}
    if(!rocellPrepareShoulder()){server.send(409,"application/json","{\"error\":\"SHOULDER_NOT_PREPARED\"}");return;}
    server.send(200,"application/json",rocellShoulderChallenge);
  });
  server.on("/rocell/shoulder-session/start",HTTP_POST,[](){
    server.sendHeader("Cache-Control","no-store");
    if(!rocellShoulderOwner||rocellShoulderStartAttempted){server.send(409,"application/json","{\"error\":\"START_UNAVAILABLE\"}");return;}
    rocellShoulderStartAttempted=true; // Never refund malformed ingress.
    if(server.args()!=1||server.argName(0)!="plain"){
      server.send(400,"application/json","{\"error\":\"EXACT_BODY_REQUIRED\"}");return;}
    const auto body=server.arg("plain");
    if(!body.length()||body.length()%2||body.length()>sizeof(rocellShoulderStartBytes)*2){
      server.send(400,"application/json","{\"error\":\"INVALID_LENGTH\"}");return;}
    for(unsigned i=0;i<body.length();++i){
      char c=body[i];int n=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
      if(n<0){server.send(400,"application/json","{\"error\":\"INVALID_HEX\"}");return;}
      if(i%2==0)rocellShoulderStartBytes[i/2]=uint8_t(n<<4);else rocellShoulderStartBytes[i/2]|=uint8_t(n);
    }
    auto admission=[](){return rocellShoulderAdmission();};
    bool ok=rocellShoulderOwner->start(rocellShoulderStartBytes,body.length()/2,rocellConfiguredClock,admission);
    memset(rocellShoulderStartBytes,0,sizeof(rocellShoulderStartBytes));
    server.send(ok?200:409,"application/json",ok?"{\"status\":\"SESSION_ACTIVATED\"}":"{\"error\":\"START_REJECTED\"}");
  });
}
void pollShoulderSession(){
  if(rocellShoulderOwner){auto admission=[](){return rocellShoulderAdmission();};
    rocellShoulderOwner->advance(st,rocellConfiguredClock,admission);}
  server.handleClient(); // Receipt transport, same task; no concurrent bus access.
}
#endif // ROCELL_LOCAL_SHOULDER_STEP

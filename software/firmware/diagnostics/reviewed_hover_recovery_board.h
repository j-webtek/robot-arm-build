// r91-only board composition. The recovery owner is the sole movement owner;
// pose observation remains acquisition-only. No startup servo read or write.
#pragma once
#include "characterization_board_services.h"
#include "characterization_evidence.h"
#include "reviewed_hover_recovery_board_adapter.h"
#include "reviewed_hover_composition.h"
#include "reviewed_hover_release_stamp.h"
#include <memory>
#include <new>

using RocellHoverEvidence=rocell_diag::CharacterizationEvidence;
using RocellHoverBase=RocellCharacterizationServices<RocellHoverEvidence>;
using RocellHoverServices=rocell_diag::ReviewedHoverRecoveryBoardAdapter<RocellHoverBase,decltype(st)>;
using RocellHoverApp=rocell_diag::ReviewedHoverComposition<rocell_diag::Esp32StartCrypto,
  RocellHoverServices,RocellConfiguredClock,WebServer,false,true>;
std::unique_ptr<RocellHoverEvidence> rocellHoverEvidence;
std::unique_ptr<RocellHoverBase> rocellHoverBase;
std::unique_ptr<RocellHoverServices> rocellHoverServices;
std::unique_ptr<RocellHoverApp> rocellHoverApp;

void registerShoulderSessionRoutes(){
  if(rocellHoverApp)return;
  constexpr size_t reserve=32768;
  constexpr size_t total=sizeof(RocellHoverEvidence)+sizeof(RocellHoverBase)+
      sizeof(RocellHoverServices)+sizeof(RocellHoverApp);
  if(ESP.getFreeHeap()<total+reserve||
     ESP.getMaxAllocHeap()<sizeof(RocellHoverEvidence))return;
  rocellHoverEvidence.reset(new(std::nothrow) RocellHoverEvidence);
  if(!rocellHoverEvidence)return;
  rocellHoverBase.reset(new(std::nothrow) RocellHoverBase{*rocellHoverEvidence});
  if(!rocellHoverBase){rocellHoverEvidence.reset();return;}
  rocellHoverServices.reset(new(std::nothrow) RocellHoverServices(*rocellHoverBase,st));
  if(!rocellHoverServices){rocellHoverBase.reset();rocellHoverEvidence.reset();return;}
  uint8_t key[32]{},boot[16]{};
  bool ready=rocellHoverBase->load_key(key)&&rocellHoverBase->boot(boot);
  if(ready)rocellHoverApp.reset(new(std::nothrow) RocellHoverApp(rocellHoldCrypto,
    *rocellHoverServices,rocellConfiguredClock,server,key,boot));
  volatile uint8_t* wipe=key;for(unsigned i=0;i<32;++i)wipe[i]=0;
  if(!rocellHoverApp||ESP.getFreeHeap()<reserve){
    rocellHoverApp.reset();rocellHoverServices.reset();
    rocellHoverBase.reset();rocellHoverEvidence.reset();return;
  }
  rocellHoverApp->register_routes();
  server.on("/rocell/recovery-hover/capabilities",HTTP_GET,[](){
    char stamp[65];
    static const char digits[]="0123456789abcdef";
    for(unsigned i=0;i<32;++i){
      const uint8_t value=rocell_diag::reviewed_hover_release_sha256[i];
      stamp[2*i]=digits[value>>4];stamp[2*i+1]=digits[value&15];
    }
    stamp[64]=0;
    char response[320];
    const int n=snprintf(response,sizeof(response),
      "{\"schema\":\"rocell.reviewed_hover_recovery_capabilities.v1\","
      "\"boot_id\":\"%s\",\"live_release_available\":true,"
      "\"motion_authorized\":false,\"maximum_legs\":5,"
      "\"stamped_release_sha256\":\"%s\"}",
      rocellDiagnosticInstance,stamp);
    server.sendHeader("Cache-Control","no-store");
    server.send(n>0&&size_t(n)<sizeof(response)?200:500,
                "application/json",n>0&&size_t(n)<sizeof(response)?response:"{}");
  });
}
void pollShoulderSession(){
  if(rocellHoverApp)rocellHoverApp->poll();
  server.handleClient();
}

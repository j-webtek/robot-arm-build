// Compile-only reviewed-hover board composition. No key provisioning, startup
// servo reads, or movement. Release identity remains unavailable by design.
#pragma once
#include "characterization_board_services.h"
#include "characterization_evidence.h"
#include "reviewed_hover_board_adapter.h"
#include "reviewed_hover_composition.h"
#include <memory>
#include <new>

using RocellHoverEvidence=rocell_diag::CharacterizationEvidence;
using RocellHoverBase=RocellCharacterizationServices<RocellHoverEvidence>;
using RocellHoverServices=rocell_diag::ReviewedHoverBoardAdapter<RocellHoverBase,decltype(st)>;
using RocellHoverApp=rocell_diag::ReviewedHoverComposition<rocell_diag::Esp32StartCrypto,
  RocellHoverServices,RocellConfiguredClock,WebServer>;
std::unique_ptr<RocellHoverEvidence> rocellHoverEvidence;
std::unique_ptr<RocellHoverBase> rocellHoverBase;
std::unique_ptr<RocellHoverServices> rocellHoverServices;
std::unique_ptr<RocellHoverApp> rocellHoverApp;

void registerShoulderSessionRoutes(){
  if(rocellHoverApp)return;
  constexpr size_t reserve=32768;
  constexpr size_t total=sizeof(RocellHoverEvidence)+sizeof(RocellHoverBase)+
      sizeof(RocellHoverServices)+sizeof(RocellHoverApp);
  if(ESP.getFreeHeap()<total+reserve||ESP.getMaxAllocHeap()<sizeof(RocellHoverEvidence))return;
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
}
void pollShoulderSession(){
  if(rocellHoverApp)rocellHoverApp->poll();
  server.handleClient();
}

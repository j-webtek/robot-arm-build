// Opt-in single-leg board composition. No startup bus read/write or provisioning.
#pragma once
#include "characterization_board_services.h"
#include "characterization_composition.h"
#include "characterization_evidence.h"
#include <memory>
#include <new>
using RocellSmokeEvidence=rocell_diag::CharacterizationEvidence;
using RocellSmokeServices=RocellCharacterizationServices<RocellSmokeEvidence>;
using RocellSmokeApp=rocell_diag::CharacterizationComposition<rocell_diag::Esp32StartCrypto,
  RocellSmokeServices,RocellConfiguredClock,WebServer>;
std::unique_ptr<RocellSmokeEvidence> rocellSmokeEvidence;
std::unique_ptr<RocellSmokeServices> rocellSmokeServices;
std::unique_ptr<RocellSmokeApp> rocellSmokeApp;
void registerShoulderSessionRoutes(){
  if(rocellSmokeApp)return;
  constexpr size_t reserve=32768;
  constexpr size_t total=sizeof(RocellSmokeEvidence)+sizeof(RocellSmokeServices)+sizeof(RocellSmokeApp);
  if(ESP.getFreeHeap()<total+reserve||ESP.getMaxAllocHeap()<sizeof(RocellSmokeEvidence))return;
  rocellSmokeEvidence.reset(new(std::nothrow) RocellSmokeEvidence);
  if(!rocellSmokeEvidence)return;
  rocellSmokeServices.reset(new(std::nothrow) RocellSmokeServices{*rocellSmokeEvidence});
  if(!rocellSmokeServices){rocellSmokeEvidence.reset();return;}
  uint8_t key[32]={},boot[16]={};
  bool ready=rocellSmokeServices->load_key(key)&&rocellSmokeServices->boot(boot);
  // Encoder-domain limits only, NOT a collision/clearance certification. A
  // physical release must review the fresh pose and narrower operating envelope.
  uint16_t bounds[7][2];for(auto& bound:bounds){bound[0]=0;bound[1]=4095;}
  if(ready)rocellSmokeApp.reset(new(std::nothrow) RocellSmokeApp(rocellHoldCrypto,
    *rocellSmokeServices,rocellConfiguredClock,server,key,boot,bounds,rocell_diag::CharacterizationPattern::Smoke));
  volatile uint8_t* wipe=key;for(unsigned i=0;i<32;++i)wipe[i]=0;
  if(!rocellSmokeApp||ESP.getFreeHeap()<reserve){
    rocellSmokeApp.reset();rocellSmokeServices.reset();rocellSmokeEvidence.reset();return;
  }
  rocellSmokeApp->register_routes();
}
void pollShoulderSession(){
  if(rocellSmokeApp)rocellSmokeApp->poll();
  server.handleClient();
}

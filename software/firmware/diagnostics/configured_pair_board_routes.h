// Included after renamed hold routes. Explicit prepare reads reviewed settings;
// nothing provisions files or supplies default motion targets/configuration.
#pragma once
#include "configured_held_pair_routes.h"
#include "controller_pair_config.h"
#include "elbow_configuration_routes.h"
#include "elbow_gain_routes.h"
#include <memory>
#include <new>
struct RocellPreparePair {
  struct Scratch {
    rocell_diag::ControllerHoldConfigParser held;
    rocell_diag::ControllerPairConfigParser pair;
    char bytes[1025]={};
  };
  bool operator()(){
#ifdef ROCELL_POSE_OBSERVATION
    if(rocellPoseReserved)return false;
#endif
    if(!rocellHoldConfigured||rocellConfiguredRuntime.state()!=rocell_diag::SessionState::Captured)
      return false;
    // Checked temporary allocation precedes all file access and hold retirement.
    // It remains alive while initialization copies policy/IDs, then frees on
    // every return path. No key material is stored in this scratch object.
    std::unique_ptr<Scratch> scratch(new(std::nothrow) Scratch());
    if(!scratch||!scratch->held.parse(rocellHoldPolicy,strlen(rocellHoldPolicy)))return false;
    File settings=LittleFS.open("/rocell-pair.json","r");
    if(!settings||settings.size()==0||settings.size()>1024){settings.close();return false;}
    const size_t length=settings.size();
    const size_t count=settings.read(reinterpret_cast<uint8_t*>(scratch->bytes),length);settings.close();
    if(count!=length||!scratch->pair.parse(scratch->bytes,length))return false;
    File key_file=LittleFS.open("/rocell-hold.key","r");
    rocell_diag::DiagnosticKeyMaterial material;
    if(!material.load(key_file)){key_file.close();return false;}key_file.close();
    uint8_t key[32]={},boot[16]={};
    if(!material.copy_to(key)){material.clear();return false;}material.clear();
    auto nibble=[](char c)->uint8_t{return c>='a'?c-'a'+10:c-'0';};
    for(size_t i=0;i<16;++i)boot[i]=(nibble(rocellDiagnosticInstance[2*i])<<4)|nibble(rocellDiagnosticInstance[2*i+1]);
    const auto& config=*scratch->held.get();
    const bool ready=rocellPairRuntime.initialize_from_hold(rocellConfiguredRuntime,st,
        rocellConfiguredClock,rocellHoldCrypto,rocellPairEntropy,config.policy,key,boot,config.port,
        scratch->pair.forward(),scratch->pair.reverse(),scratch->pair.offset(),scratch->pair.tolerance(),rocellHoldHealthy,nullptr);
    volatile uint8_t* wipe=key;for(size_t i=0;i<32;++i)wipe[i]=0;
    return ready;
  }
};
RocellPreparePair rocellPreparePair;
rocell_diag::ConfiguredHeldPairRoutes<RocellPairRuntime,RocellPreparePair,WebServer>
    rocellPairRoutes(rocellPairRuntime,rocellPreparePair,server);
bool rocellConfigurationBusInactive(void*){
#ifdef ROCELL_POSE_OBSERVATION
  if(rocellPoseReserved)return false;
#endif
#ifdef ROCELL_RECOVERY_DIAGNOSTIC_OWNER
  if(rocellRecoveryRuntime.exclusive_work()||
     rocellRecoveryRuntime.state()==rocell_diag::SessionState::Sampling)return false;
#endif
  if(rocellConfiguredRuntime.exclusive_work()||rocellPairRuntime.exclusive_work())return false;
  if(rocellConfiguredRuntime.state()==rocell_diag::SessionState::Sampling)return false;
  const auto phase=rocellPairRuntime.phase();
  return phase==rocell_diag::PairNetworkPhase::New||
         phase==rocell_diag::PairNetworkPhase::Complete||phase==rocell_diag::PairNetworkPhase::Fault;
}
rocell_diag::ElbowConfigurationRoutes<decltype(st),decltype(rocellConfiguredClock),WebServer>
    rocellConfigurationRoutes(st,rocellConfiguredClock,server,rocellDiagnosticInstance,rocellConfigurationBusInactive);
// Separate retained capture: never acquires at startup or while motion owns the bus.
rocell_diag::ElbowGainRoutes<decltype(st),decltype(rocellConfiguredClock),WebServer>
    rocellGainRoutes(st,rocellConfiguredClock,server,rocellDiagnosticInstance,rocellConfigurationBusInactive);
#ifdef ROCELL_RECOVERY_DIAGNOSTIC_OWNER
#include "configured_recovery_board_routes.h"
#endif
#ifdef ROCELL_POSE_OBSERVATION
#include "pose_observation_board.h"
#endif
void registerDiagnosticRoutes(){
  registerHoldDiagnosticRoutes();
#ifdef ROCELL_POSE_OBSERVATION
  registerPoseObservationRoutes();
#endif
  rocellPairRoutes.register_routes();
  rocellConfigurationRoutes.register_routes();
  rocellGainRoutes.register_routes();
#ifdef ROCELL_RECOVERY_DIAGNOSTIC_OWNER
  rocellRecoveryRoutes.register_routes();
#endif
  server.on("/rocell/held-pair/capabilities",HTTP_GET,[](){
    // Read-only resource snapshot. Does not open files, retire hold, or touch bus.
    char response[768];
    snprintf(response,sizeof(response),
      "{\"schema\":\"rocell.held_pair_capabilities.v1\",\"boot_id\":\"%s\","
      "\"protocol\":\"hold-first-pair-v1\",\"servo_id\":14,\"max_offset_counts\":16,"
      "\"free_internal_heap_bytes\":%lu,\"minimum_free_internal_heap_bytes\":%lu,"
      "\"largest_internal_block_bytes\":%lu,\"stack_measured\":false,\"physical_accuracy_verified\":false}",
      rocellDiagnosticInstance,(unsigned long)ESP.getFreeHeap(),
      (unsigned long)ESP.getMinFreeHeap(),(unsigned long)ESP.getMaxAllocHeap());
    server.sendHeader("Cache-Control","no-store");server.send(200,"application/json",response);
  });
}

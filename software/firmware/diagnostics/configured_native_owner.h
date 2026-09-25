// Included after the pinned arm module. Static runtime; no startup movement.
#pragma once
#define ROCELL_NATIVE_DIAGNOSTIC_OWNER 1
#define ROCELL_CONFIGURED_DIAGNOSTIC_OWNER 1
#include <esp_timer.h>
#include <NetworkServer.h>
#include "reference_elbow_admission.h"
#include "start_crypto_esp32.h"
#include "start_socket_esp32.h"
#include "configured_diagnostic_runtime.h"
bool rocellOwnerFault();
struct RocellConfiguredClock {uint64_t now_us(){return static_cast<uint64_t>(esp_timer_get_time());}};
using RocellConfiguredRuntime=rocell_diag::ConfiguredDiagnosticRuntime<SMS_STS,RocellConfiguredClock,
    NetworkServer,NetworkClient,rocell_diag::Esp32StartSocket,rocell_diag::ReferenceElbowAdmission,rocell_diag::Esp32StartCrypto>;
RocellConfiguredRuntime rocellConfiguredRuntime;
RocellConfiguredClock rocellConfiguredClock;
auto& rocellDiagnosticSession=rocellConfiguredRuntime;
auto& rocellDiagnosticEvidence=rocellConfiguredRuntime;
char rocellDiagnosticInstance[33]={};
bool rocellDiagnosticOwned=false;
bool rocellConfiguredFault(void*){return rocellOwnerFault();}
bool rocellRejectDiagnosticInterference(){
  if(!rocellDiagnosticOwned)return false;
  rocellConfiguredRuntime.interference();return true;
}
void pollReceivedDiagnostic(){rocellConfiguredRuntime.poll();}
void registerConfiguredChallengeRoute();

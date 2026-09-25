// Hold-only board composition. Construction performs no bus or network I/O.
#pragma once
#define ROCELL_NATIVE_DIAGNOSTIC_OWNER 1
#define ROCELL_CONFIGURED_DIAGNOSTIC_OWNER 1
#include <esp_timer.h>
#include <NetworkServer.h>
#include "start_crypto_esp32.h"
#include "start_socket_esp32.h"
#include "configured_hold_runtime.h"
#include "controller_diagnostic_config.h"
bool rocellOwnerFault();
struct RocellConfiguredClock {uint64_t now_us(){return uint64_t(esp_timer_get_time());}};
using RocellConfiguredRuntime=rocell_diag::ConfiguredHoldRuntime<SMS_STS,RocellConfiguredClock,
    NetworkServer,NetworkClient,rocell_diag::Esp32StartSocket,rocell_diag::Esp32StartCrypto>;
RocellConfiguredRuntime rocellConfiguredRuntime;
RocellConfiguredClock rocellConfiguredClock;
rocell_diag::Esp32StartCrypto rocellHoldCrypto;
char rocellDiagnosticInstance[33]={};
bool rocellDiagnosticOwned=false;
bool rocellHoldHealthy(void*){return !rocellOwnerFault();}
bool rocellRejectDiagnosticInterference(){
  if(!rocellDiagnosticOwned)return false;
  rocellConfiguredRuntime.interference();return true;
}
void pollReceivedDiagnostic(){rocellConfiguredRuntime.poll();}

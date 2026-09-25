// Included after hold owner declarations. No constructor performs I/O.
#pragma once
#include "configured_held_pair_runtime.h"
#include "held_pair_entropy_esp32.h"
using RocellPairRuntime=rocell_diag::ConfiguredHeldPairRuntime<SMS_STS,RocellConfiguredClock,
    rocell_diag::Esp32StartCrypto,rocell_diag::Esp32PairEntropy,
    NetworkServer,NetworkClient,rocell_diag::Esp32StartSocket>;
RocellPairRuntime rocellPairRuntime;
rocell_diag::Esp32PairEntropy rocellPairEntropy;

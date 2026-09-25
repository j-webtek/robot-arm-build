// Compile-only ESP32 ABI probe. Never linked into or uploaded as firmware.
#include "hold_authenticated_runtime.h"
#include "evidence_store.h"
#include "allocated_hold_runtime.h"
#include "configured_hold_runtime.h"
struct ProbeBus {
 int End=0,Level=1,Error=0;
 int Read(uint8_t,uint8_t,uint8_t*,uint8_t);
 int WritePosEx(uint8_t,int16_t,uint16_t,uint8_t);
 int EnableTorque(uint8_t,uint8_t);
};
struct ProbeClock {uint64_t now_us();};
struct ProbeCrypto {
 bool sha256(const uint8_t*,size_t,uint8_t (&)[32]);
 bool hmac_sha256(const uint8_t (&)[32],const uint8_t*,size_t,uint8_t (&)[32]);
};
struct ProbeClient {int fd()const;void stop();};
struct ProbeServer {
 ProbeServer(uint16_t,int);void begin();void end();explicit operator bool()const;
 ProbeClient accept();
};
struct ProbeSocket {
 explicit ProbeSocket(ProbeClient&);int receive(uint8_t*,size_t);
 int send_once(const uint8_t*,size_t);void close();
};
using Store=rocell_diag::EvidenceStore<12,4096>;
using Runtime=rocell_diag::HoldAuthenticatedRuntime<ProbeBus,ProbeClock,Store,ProbeCrypto>;
template class rocell_diag::HoldAuthenticatedRuntime<ProbeBus,ProbeClock,Store,ProbeCrypto>;
using Allocated=rocell_diag::AllocatedHoldRuntime<ProbeBus,ProbeClock,ProbeCrypto>;
template class rocell_diag::AllocatedHoldRuntime<ProbeBus,ProbeClock,ProbeCrypto>;
using Configured=rocell_diag::ConfiguredHoldRuntime<ProbeBus,ProbeClock,ProbeServer,ProbeClient,ProbeSocket,ProbeCrypto>;
template class rocell_diag::ConfiguredHoldRuntime<ProbeBus,ProbeClock,ProbeServer,ProbeClient,ProbeSocket,ProbeCrypto>;
// nm -S reports array byte sizes without running target code on the host.
extern "C" {
char hold_probe_snapshot[sizeof(rocell_diag::HoldStateSnapshot)];
char hold_probe_owner[sizeof(rocell_diag::HoldInitializationOwner)];
char hold_probe_publisher[sizeof(rocell_diag::HoldEvidencePublisher)];
char hold_probe_admission[sizeof(rocell_diag::HoldPlanAdmission)];
char hold_probe_runtime[sizeof(Runtime)];
char hold_probe_store[sizeof(Store)];
char hold_probe_runtime_store[sizeof(Runtime)+sizeof(Store)];
char hold_probe_allocated_wrapper[sizeof(Allocated)];
char hold_probe_allocation[Allocated::allocation_bytes()];
char hold_probe_configured_allocation[Configured::allocation_bytes()];
}

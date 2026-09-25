// Compile-only target-ABI probe. Never link, flash, or execute these arrays.
#include <SCServo.h>
#include "held_pair_authenticated_runtime.h"
#include "held_pair_transport_json.h"
#include "held_pair_listener_owner.h"
#include "start_socket_session.h"
#include "start_listener.h"
#include "held_pair_network_operation.h"
#include "start_socket_esp32.h"
#include <NetworkServer.h>
#include "held_pair_network_lifecycle.h"
#include "held_pair_entropy_esp32.h"
#include "allocated_hold_runtime.h"
#include "configured_hold_runtime.h"
#include "configured_held_pair_runtime.h"
#include <WebServer.h>
#include "configured_held_pair_routes.h"
struct ProbeClock { uint64_t now_us(); };
struct ProbeCrypto {
  bool sha256(const uint8_t*,size_t,uint8_t (&)[32]);
  bool hmac_sha256(const uint8_t (&)[32],const uint8_t*,size_t,uint8_t (&)[32]);
};
using namespace rocell_diag;
using Runtime=HeldPairAuthenticatedRuntime<SMS_STS,ProbeClock,ProbeCrypto>;
using Bridge=HeldPairReturnBridge<Runtime::Store,ProbeCrypto,ProbeClock>;
struct ProbeSocket {int receive(uint8_t*,size_t);int send_once(const uint8_t*,size_t);void close();};
struct ProbeClient {int fd();void stop();};
struct ProbeServer {void begin();void end();explicit operator bool();ProbeClient accept();};
using Operation=HeldPairInitialOperation<Runtime>;
using Owner=HeldPairListenerOwner<Runtime,Operation>;
using Connection=StartSocketSession<Owner,ProbeClock,ProbeSocket>;
using Listener=StartListener<ProbeServer,ProbeClient,Connection,Owner,ProbeClock>;
using DeviceNetwork=HeldPairNetworkOperation<Runtime,Operation,ProbeClock,NetworkServer,NetworkClient,Esp32StartSocket>;
using DeviceLifecycle=HeldPairNetworkLifecycle<Runtime,ProbeClock,Esp32PairEntropy,NetworkServer,NetworkClient,Esp32StartSocket>;
using DeviceHold=ConfiguredHoldRuntime<SMS_STS,ProbeClock,NetworkServer,NetworkClient,Esp32StartSocket,ProbeCrypto>;
using DevicePair=ConfiguredHeldPairRuntime<SMS_STS,ProbeClock,ProbeCrypto,Esp32PairEntropy,NetworkServer,NetworkClient,Esp32StartSocket>;
struct ProbePrepare {bool operator()();};
using DeviceRoutes=ConfiguredHeldPairRoutes<DevicePair,ProbePrepare,WebServer>;
template class rocell_diag::ConfiguredHeldPairRoutes<DevicePair,ProbePrepare,WebServer>;
void probe_loop(DeviceHold& hold,DevicePair& pair,WebServer& web){poll_hold_pair_diagnostics(hold,pair,web);}
template class rocell_diag::ConfiguredHeldPairRuntime<SMS_STS,ProbeClock,ProbeCrypto,Esp32PairEntropy,NetworkServer,NetworkClient,Esp32StartSocket>;
bool probe_transition(DevicePair& pair,DeviceHold& hold,SMS_STS& bus,ProbeClock& clock,
    ProbeCrypto& crypto,Esp32PairEntropy& entropy,const HoldInitializationPolicy& policy,
    const uint8_t (&key)[32],const uint8_t (&boot)[16],bool (*healthy)(void*),void* context){
  return pair.initialize_from_hold(hold,bus,clock,crypto,entropy,policy,key,boot,8081,
      "forward","return",6,2,healthy,context);
}
// Instantiate methods as well as measuring layout, catching target-only errors.
template class rocell_diag::HeldPairAuthenticatedRuntime<SMS_STS,ProbeClock,ProbeCrypto>;
template class rocell_diag::HeldPairListenerOwner<Runtime,Operation>;
template class rocell_diag::StartSocketSession<Owner,ProbeClock,ProbeSocket>;
template class rocell_diag::StartListener<ProbeServer,ProbeClient,Connection,Owner,ProbeClock>;
template class rocell_diag::HeldPairNetworkOperation<Runtime,Operation,ProbeClock,NetworkServer,NetworkClient,Esp32StartSocket>;
template class rocell_diag::HeldPairNetworkLifecycle<Runtime,ProbeClock,Esp32PairEntropy,NetworkServer,NetworkClient,Esp32StartSocket>;
bool probe_status(const Runtime& r,char* out,size_t n){return held_pair_status_json(r,out,n);}
bool probe_record(const Runtime& r,size_t i,char* out,size_t n){return held_pair_record_json(r,i,out,n);}
extern "C" {
unsigned char rocell_size_pair_runtime[sizeof(Runtime)];
unsigned char rocell_size_pair_owner[sizeof(HeldElbowPairOwner)];
unsigned char rocell_size_leg_owner[sizeof(HeldElbowLegOwner)];
unsigned char rocell_size_snapshot[sizeof(HoldStateSnapshot)];
unsigned char rocell_size_evidence_store[sizeof(Runtime::Store)];
unsigned char rocell_size_publisher[sizeof(HeldLegEvidencePublisher)];
unsigned char rocell_size_return_bridge[sizeof(Bridge)];
unsigned char rocell_size_initial_gate[sizeof(HeldPairPlanAdmission)];
unsigned char rocell_size_return_gate[sizeof(HeldReturnAdmission)];
unsigned char rocell_size_hold_owner[sizeof(HoldInitializationOwner)];
unsigned char rocell_size_pair_connection[sizeof(Connection)];
unsigned char rocell_size_pair_listener[sizeof(Listener)];
unsigned char rocell_size_verified_handoff[sizeof(VerifiedHoldHandoff)];
unsigned char rocell_size_device_network[sizeof(DeviceNetwork)];
unsigned char rocell_size_device_lifecycle[sizeof(DeviceLifecycle)];
unsigned char rocell_size_initial_network_graph[DeviceLifecycle::initial_graph_bytes()];
unsigned char rocell_size_return_network_graph[DeviceLifecycle::return_graph_bytes()];
}

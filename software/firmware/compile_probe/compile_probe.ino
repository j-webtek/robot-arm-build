// Compile/link probe only. No serial initialization, device access or motion.
#include <FS.h>
#include "command_capture.h"
#include "callback_handoff.h"
#include "reference_read_adapter.h"
#include "reference_write_capture.h"
#include <SMS_STS.h>
#include "diagnostic_session.h"
#include "evidence_store.h"
#include "diagnostic_receipt.h"
#include "received_session.h"
#include "start_envelope.h"
#include "start_crypto_esp32.h"
#include "start_plan_structure.h"
#include "authorized_start.h"
#include "whole_arm_baseline.h"
#include "whole_arm_baseline_json.h"
#include "admitted_session.h"
#include "shoulder_preload_session.h"
#include "shoulder_export_receipt.h"
#include "shoulder_session_owner.h"

// Target-platform signature/resource probe, never invoked by setup or loop.
// Synthetic key only. Keep the ~9 KB session off the control task's stack.
rocell_diag::Esp32StartCrypto shoulder_probe_crypto;
const uint8_t shoulder_probe_key[32]={1},shoulder_probe_boot[16]={};
volatile bool shoulder_probe_admitted=false;
rocell_diag::ShoulderBusReservation shoulder_owner_reservation;
const uint8_t shoulder_owner_nonce[32]={};
rocell_diag::ShoulderSessionOwner<rocell_diag::Esp32StartCrypto> shoulder_owner_probe(
    shoulder_probe_crypto,shoulder_owner_reservation,shoulder_probe_key,shoulder_probe_boot,
    shoulder_owner_nonce,0,30000000,"compile-owner",rocell_diag::ShoulderSessionScope::PairHold);

struct FakeBus {
  unsigned char Error=0;
  int Read(uint8_t,uint8_t,uint8_t* bytes,uint8_t width) {
    for (uint8_t i=0;i<width;++i) bytes[i]=0;
    return width;
  }
};
struct FakeClock { uint64_t value=1000; uint64_t now_us() { return ++value; } };
void shoulder_native_compile_probe(SMS_STS& bus,const uint8_t* token,size_t length){
  FakeClock clock;auto admission=[](){return shoulder_probe_admitted;};
  shoulder_owner_probe.start(token,length,clock,admission);
  shoulder_owner_probe.advance(bus,clock,admission);
  if(auto* session=shoulder_owner_probe.session())
    session->receipt(rocell_diag::ShoulderReceiptView{token,length},clock.now_us());
}
void (*volatile shoulder_native_probe_address)(SMS_STS&,const uint8_t*,size_t)=shoulder_native_compile_probe;

// Kept in the linked image to check atomics/printf and template instantiations.
__attribute__((used)) bool diagnostic_compile_probe() {
  FakeBus library;FakeClock clock;
  rocell_diag::ReferenceReadAdapter<FakeBus> adapter(library);
  rocell_diag::CommandCapture capture;rocell_diag::PairEvidence pair;
  rocell_diag::CallbackHandoff<4> handoff;
  const uint8_t sender[6]={},data[4]={};
  char output[2048];
  return handoff.push(sender,data,4) &&
      capture.begin("probe","command",14,2100,20,1,1000,1,0,
          rocell_diag::AckPolicy::Enabled,1,100) &&
      capture.acquire(adapter,clock,pair) &&
      capture.encode_pair("little",output,sizeof(output));
}
bool (*volatile probe_address)()=diagnostic_compile_probe;
// Compile the hook against the actual pinned library signature, not only a fake.
// This function is retained but never called by setup/loop; no native I/O occurs.
bool native_signature_probe(SMS_STS& library) {
  FakeClock clock;rocell_diag::ReferenceWriteCapture hook;
  return hook.dispatch(library,clock,"probe","command",14,2100,20,1,1,100);
}
bool (*volatile native_probe_address)(SMS_STS&)=native_signature_probe;
rocell_diag::EvidenceStore<8> probe_evidence_store;
bool native_session_probe(SMS_STS& library) {
  FakeClock clock;auto& sink=probe_evidence_store;rocell_diag::DiagnosticSession session;
  return session.start(library,clock,sink,"probe","session",14,2100,20,1,1,100) &&
      session.sample(library,clock,sink);
}
bool (*volatile session_probe_address)(SMS_STS&)=native_session_probe;
bool receipt_probe() {
  rocell_diag::DiagnosticReceipt receipt;char output[2048];
  const char* payload="{\"T\":101,\"joint\":3,\"rad\":1.7,\"spd\":20,\"acc\":1}";
  return receipt.accept("probe","receipt",payload,strlen(payload),1000) &&
      receipt.encode(output,sizeof(output));
}
bool (*volatile receipt_probe_address)()=receipt_probe;
struct ProbeAdmission {
  bool admit_and_convert(double,uint16_t,uint8_t,uint16_t& target){target=2100;return true;}
};
bool reject_probe_boundary(void*,uint64_t){return false;}
bool received_session_probe(SMS_STS& library) {
  rocell_diag::ReceivedSession session;FakeClock clock;ProbeAdmission admission;
  const char* payload="{\"T\":101,\"joint\":3,\"rad\":1.7,\"spd\":20,\"acc\":1}";
  return session.start(library,clock,probe_evidence_store,admission,"probe","received",
                       payload,strlen(payload),1,100,1000000,
                       rocell_diag::WriteBoundaryGuard{reject_probe_boundary,nullptr});
}
bool (*volatile received_probe_address)(SMS_STS&)=received_session_probe;
void setup() {
  (void)probe_address;
  (void)shoulder_native_probe_address; // Volatile read retains code, never calls it.
}
void loop() {}
bool start_crypto_probe(const uint8_t* token,size_t size) {
  uint8_t key[32]={1},boot[16]={},nonce[32]={};
  rocell_diag::StartEnvelopeGate gate(key,boot,nonce,1,100);
  rocell_diag::Esp32StartCrypto crypto;rocell_diag::AuthenticatedPlanView view;
  return gate.consume(token,size,2,crypto,view);
}
bool (*volatile start_crypto_probe_address)(const uint8_t*,size_t)=start_crypto_probe;
bool start_plan_probe(const char* bytes,size_t length) {
  rocell_diag::StartPlanStructure parser;
  rocell_diag::Esp32StartCrypto crypto;ProbeAdmission converter;
  return parser.parse(bytes,length,"11111111111111111111111111111111","probe-reference") &&
      parser.bind_payload(crypto,converter);
}
bool (*volatile start_plan_probe_address)(const char*,size_t)=start_plan_probe;
struct ProbeClearance {bool check(const rocell_diag::BoundStartRequest&){return false;}};
struct ProbeStarter {bool start(const rocell_diag::BoundStartRequest&){return false;}};
bool authorized_start_probe(const uint8_t* token,size_t length) {
  uint8_t key[32]={1},boot[16]={},nonce[32]={};
  rocell_diag::AuthorizedStart owner(key,boot,nonce,1000,11000,"probe-reference");
  FakeClock clock;rocell_diag::Esp32StartCrypto crypto;ProbeAdmission converter;
  ProbeClearance admission;ProbeStarter starter;
  return owner.start(token,length,clock,crypto,converter,probe_evidence_store,admission,starter);
}
bool (*volatile authorized_start_probe_address)(const uint8_t*,size_t)=authorized_start_probe;
bool whole_arm_baseline_probe(SMS_STS& library) {
  rocell_diag::WholeArmBaselinePolicy policy={};
  for(auto& joint:policy.joints)joint={1990,2010}; // Synthetic compile fixture only.
  policy.tracking_tolerance=2;policy.maximum_pair_us=1000;
  policy.maximum_scan_us=10000;policy.maximum_age_us=10000;
  rocell_diag::WholeArmBaseline gate(policy);FakeClock clock;
  char output[2048];
  return gate.check(library,clock) &&
      rocell_diag::whole_arm_baseline_json(gate,"probe","whole-arm",output,sizeof(output));
}
bool (*volatile whole_arm_probe_address)(SMS_STS&)=whole_arm_baseline_probe;
bool probe_owner_fault(void*){return true;}
bool admitted_session_probe(SMS_STS& library) {
  FakeClock clock;ProbeAdmission converter;rocell_diag::WholeArmBaselinePolicy policy={};
  rocell_diag::AdmittedSession<SMS_STS,FakeClock,rocell_diag::EvidenceStore<8>,ProbeAdmission> session(
      library,clock,probe_evidence_store,converter,policy,11000,probe_owner_fault,nullptr);
  rocell_diag::BoundStartRequest request;
  return session.check(request) && session.start(request) && session.sample();
}
bool (*volatile admitted_session_probe_address)(SMS_STS&)=admitted_session_probe;
#include "authenticated_diagnostic_owner.h"
#include "diagnostic_status_json.h"
#include "start_request_body.h"
#include "start_http_request.h"
#include "start_socket_session.h"
#include "start_socket_esp32.h"
#include "start_listener.h"
#include <NetworkServer.h>
bool authenticated_owner_probe(SMS_STS& library) {
  FakeClock clock;ProbeAdmission converter;rocell_diag::Esp32StartCrypto crypto;
  rocell_diag::WholeArmBaselinePolicy policy={};
  uint8_t key[32]={1},boot[16]={},nonce[32]={};
  rocell_diag::AuthenticatedDiagnosticOwner<SMS_STS,FakeClock,rocell_diag::EvidenceStore<8>,ProbeAdmission,
      rocell_diag::Esp32StartCrypto> owner(library,clock,probe_evidence_store,converter,crypto,
      key,boot,nonce,1000,11000,"probe-reference",policy,probe_owner_fault,nullptr);
  NetworkClient client;rocell_diag::Esp32StartSocket socket(client);
  rocell_diag::StartSocketSession<decltype(owner),FakeClock,rocell_diag::Esp32StartSocket> connection(owner,clock,socket);
  NetworkServer server(8081,1);
  rocell_diag::StartListener<NetworkServer,NetworkClient,decltype(connection),decltype(owner),FakeClock> listener(
      server,client,connection,owner,clock,11000);
  // This entire probe is retained for linking only; never called by setup/loop.
  listener.begin();listener.poll();
  owner.sample();owner.export_failed();
  char output[512];
  return rocell_diag::diagnostic_status_json(owner,probe_evidence_store,"11111111111111111111111111111111",output,sizeof(output));
}
bool (*volatile authenticated_owner_probe_address)(SMS_STS&)=authenticated_owner_probe;
#include "controller_diagnostic_config.h"
bool controller_config_probe(const char* bytes,size_t length,fs::File& key_file){
  rocell_diag::ControllerDiagnosticConfigParser parser;rocell_diag::DiagnosticKeyMaterial key;
  uint8_t material[32]={};
  const bool ok=parser.parse(bytes,length,"probe-reference") && key.load(key_file) && key.copy_to(material);
  volatile uint8_t* wipe=material;for(size_t i=0;i<32;++i)wipe[i]=0;
  return ok;
}
bool (*volatile controller_config_probe_address)(const char*,size_t,fs::File&)=controller_config_probe;
#include "configured_diagnostic_runtime.h"
struct ConfigProbeConverter {
  struct Bounds {double low,high;uint16_t speed;uint8_t acceleration;};
  explicit ConfigProbeConverter(Bounds){}
  bool admit_and_convert(double,uint16_t,uint8_t,uint16_t&){return false;}
};
using ProbeConfiguredRuntime=rocell_diag::ConfiguredDiagnosticRuntime<SMS_STS,FakeClock,NetworkServer,
    NetworkClient,rocell_diag::Esp32StartSocket,ConfigProbeConverter,rocell_diag::Esp32StartCrypto>;
ProbeConfiguredRuntime configured_runtime_probe_storage;
bool configured_runtime_probe(SMS_STS& library){
  static FakeClock clock;rocell_diag::DiagnosticKeyMaterial missing_key;
  uint8_t boot[16]={},nonce[32]={};
  bool result=configured_runtime_probe_storage.initialize(library,clock,"{}",2,"probe-reference",missing_key,
      boot,nonce,probe_owner_fault,nullptr);
  configured_runtime_probe_storage.poll();return result;
}
bool (*volatile configured_runtime_probe_address)(SMS_STS&)=configured_runtime_probe;

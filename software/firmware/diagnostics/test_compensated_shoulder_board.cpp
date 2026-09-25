// Real board-adapter handlers + native owner/crypto, fake platform/files/bus.
#define NOMINMAX
#define main crypto_test_main
#include "test_shoulder_export_receipt.cpp"
#undef main
#define main preload_test_main
#include "test_shoulder_preload_candidate.cpp"
#undef main
#include <map>
#include <functional>
constexpr int HTTP_GET=0,HTTP_POST=1;
struct WebServer {
 std::map<std::string,std::function<void()>> routes;
 int parameters=0,status=0;std::string body,name="plain",response;
 void on(const char* p,int,std::function<void()> f){routes[p]=f;}
 int args(){return parameters;}std::string argName(int){return name;}std::string arg(const char*){return body;}
 void sendHeader(const char*,const char*){}void send(int s,const char*,const char* p){status=s;response=p;}
 void handleClient(){}
} server;
struct File {void close(){}};
struct Files {int opens=0;File open(const char* path,const char* mode){
 assert(std::string(path)=="/rocell-hold.key"&&std::string(mode)=="r");++opens;return {};
}} LittleFS;
bool missing_key=false,healthy=true,bus_idle=true;
namespace rocell_diag {
using Esp32StartCrypto=::Crypto;
enum class PairNetworkPhase {New,Other};
struct DiagnosticKeyMaterial {
 bool load(File&){return !missing_key;}
 bool copy_to(uint8_t (&key)[32]){for(int i=0;i<32;++i)key[i]=i;return true;}
 void clear(){}
};
}
bool rocellShoulderReserved=false,rocellDiagnosticOwned=false,rocellPoseReserved=false,
 rocellHoldChallengeAttempted=false,rocellHoldConfigured=false,rocellRecoveryReserved=false;
struct Pair {auto phase(){return rocell_diag::PairNetworkPhase::New;}} rocellPairRuntime;
bool rocellHoldHealthy(void*){return healthy;}
bool rocellConfigurationBusInactive(void*){return bus_idle;}
using RocellConfiguredClock=Clock;
Clock rocellConfiguredClock;Crypto rocellHoldCrypto;Bus st;
char rocellDiagnosticInstance[33]="11111111111111111111111111111111";
void esp_fill_random(void* bytes,size_t count){memset(bytes,0,count);}
#if defined(ROCELL_COMPENSATED_SHOULDER_STEP)
struct FakeESP {
 size_t free_bytes=200000,largest=100000;
 size_t getFreeHeap(){return free_bytes;}size_t getMaxAllocHeap(){return largest;}
} ESP;
#endif
#include "shoulder_board_session.h"
int main(int argc,char** argv){
 assert(argc==2);std::string mode=argv[1];
#if defined(ROCELL_COMPENSATED_SHOULDER_STEP)
 registerShoulderSessionRoutes();assert(server.routes.size()==9);
 assert(server.routes.count("/rocell/shoulder-session/start")==0);
 assert(!rocellCompensatedSession&&st.reads==0&&st.writes==0);
 assert(!rocellCompensatedMemoryFits(0,1000000));assert(!rocellCompensatedMemoryFits(1000000,1));
 if(mode=="conflict")rocellPoseReserved=true;
 if(mode=="missing_key")missing_key=true;
 if(mode=="unhealthy")healthy=false;
 if(mode=="busy")bus_idle=false;
 if(mode=="parameters")server.parameters=1;
 if(mode=="low_heap")ESP.free_bytes=1;
 if(mode=="fragmented")ESP.largest=1;
 auto prepare=server.routes.at("/rocell/compensated-step/prepare");
 auto authorize=server.routes.at("/rocell/compensated-step/authorize");
 prepare();assert(st.reads==0&&st.writes==0);
 if(mode=="conflict"||mode=="missing_key"||mode=="unhealthy"||mode=="busy"||mode=="parameters"||mode=="low_heap"||mode=="fragmented"){
   assert(server.status==409||server.status==400);assert(!rocellCompensatedSession);
 }else{
   assert(server.status==200&&rocellCompensatedSession&&rocellCompensatedSettling);
   prepare();assert(server.status==409);
   server.parameters=1;server.body=std::string(248,'0');authorize();assert(server.status==409);
   server.parameters=0;
   if(mode=="admission_lost")healthy=false;
   pollShoulderSession();assert(st.reads==(mode=="admission_lost"?0:28)&&st.writes==0);
   server.routes.at("/rocell/compensated-step/status")();assert(server.status==200);
   assert(rocellShoulderReserved&&rocellDiagnosticOwned);
 }
 std::cout<<"LOCAL_OBJECT_BYTES "<<sizeof(RocellCompensatedSession)<<" "<<sizeof(RocellCompensatedSettling)<<"\n";
 std::cout<<"BOARD_INGRESS_OFFLINE_PASSED\n";
#else
 registerShoulderSessionRoutes();
#if defined(ROCELL_FAULT_SETTLING_CAPTURE)
 assert(server.routes.size()==9);
 server.routes.at("/rocell/shoulder-settling/status")();assert(server.status==409);
#else
 assert(server.routes.size()==5);
#endif
 auto prepare=server.routes.at("/rocell/shoulder-session/prepare");
 auto start=server.routes.at("/rocell/shoulder-session/start");
 if(mode=="conflict")rocellPoseReserved=true;
 if(mode=="missing_key")missing_key=true;
 if(mode=="unhealthy")healthy=false;
 if(mode=="busy")bus_idle=false;
 if(mode=="parameters")server.parameters=1;
 prepare();assert(st.reads==0&&st.writes==0);
 if(mode=="conflict"||mode=="missing_key"||mode=="unhealthy"||mode=="busy"||mode=="parameters"){
   assert(server.status==409||server.status==400);
   assert(!rocellShoulderOwner);
   if(mode=="missing_key"){assert(rocellShoulderReserved);prepare();assert(LittleFS.opens==1);}
   else assert(LittleFS.opens==0);
 }else{
   assert(server.status==200&&rocellShoulderReserved&&LittleFS.opens==1);
   prepare();assert(server.status==409&&LittleFS.opens==1);
   server.parameters=1;
   const char domain[]="rocell.diagnostic-start.v1";
   std::vector<uint8_t> bytes(domain,domain+sizeof(domain));
   bytes.insert(bytes.end(),16,0x11);bytes.insert(bytes.end(),32,0);
   for(uint64_t t:{uint64_t(101),uint64_t(30000101)})for(int i=7;i>=0;--i)bytes.push_back(uint8_t(t>>(8*i)));
   std::string plan=rocellShoulderOwner->canonical_plan();
#if defined(ROCELL_STABLE_CLEARANCE_RECOVERY)
   assert(plan.find("STABLE_CLEARANCE_RECOVERY")!=std::string::npos&&plan.find("shoulder-stable-clearance24-v1")!=std::string::npos);
#elif defined(ROCELL_CLEARANCE_RECOVERY)
   assert(plan.find("CLEARANCE_RECOVERY")!=std::string::npos&&plan.find("shoulder-clearance24-v1")!=std::string::npos);
#elif defined(ROCELL_SHOULDER_RISE)
   assert(plan.find("SHOULDER_RISE")!=std::string::npos&&plan.find("shoulder-rise12-v1")!=std::string::npos);
#elif defined(ROCELL_POSE_PREPARATION)
   assert(plan.find("POSE_PREPARATION")!=std::string::npos&&plan.find("pose-preparation-v1")!=std::string::npos);
#elif defined(ROCELL_MIXED_TARGET_EXPERIMENT)
   assert(plan.find("MIXED_TARGET")!=std::string::npos&&plan.find("mixed-shoulder-target-v1")!=std::string::npos);
#else
   assert(plan.find("PAIR_HOLD")!=std::string::npos);
#endif
   bytes.push_back(plan.size()>>8);bytes.push_back(plan.size()&255);bytes.insert(bytes.end(),plan.begin(),plan.end());
   uint8_t key[32],digest[32];for(int i=0;i<32;++i)key[i]=i;
   assert(rocellHoldCrypto.hmac_sha256(key,bytes.data(),bytes.size(),digest));bytes.insert(bytes.end(),digest,digest+32);
   const char* digits="0123456789abcdef";
   for(auto b:bytes){server.body+=digits[b>>4];server.body+=digits[b&15];}
   if(mode=="malformed")server.body="xx";
   if(mode=="oversize")server.body=std::string(1026,'0');
   if(mode=="tampered")server.body.back()=server.body.back()=='0'?'1':'0';
   if(mode=="expired")rocellConfiguredClock.tick=30000200;
   if(mode=="admission_lost")healthy=false;
   start();assert(st.reads==0&&st.writes==0);
   if(mode=="success"){
     assert(server.status==200&&rocellShoulderOwner->session());
     assert(!rocellShoulderOwner->settling());
     pollShoulderSession();assert(st.reads==28&&st.writes==0);
#if defined(ROCELL_FAULT_SETTLING_CAPTURE)
     healthy=false;pollShoulderSession();
     assert(rocellShoulderOwner->session()->phase()==rocell_diag::ShoulderPreloadPhase::Fault);
     assert(rocellShoulderOwner->settling());
     assert(rocellShoulderOwner->settling()->state()==rocell_diag::SettlingState::Idle);
     pollShoulderSession();assert(st.reads==28&&st.writes==0);
     assert(rocellShoulderReserved&&rocellDiagnosticOwned);
#endif
   }else assert(server.status==400||server.status==409);
   start();assert(server.status==409&&st.writes==0);
 }
 std::cout<<"BOARD_INGRESS_OFFLINE_PASSED\n";
#endif
}

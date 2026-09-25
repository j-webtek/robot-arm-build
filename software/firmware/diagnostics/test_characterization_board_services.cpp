#define main admission_fixture_main
#include "test_characterization_admission.cpp"
#undef main
struct File{void close(){}};
struct Files{unsigned opens=0;File open(const char* path,const char* mode){
 assert(std::string(path)=="/rocell-hold.key"&&std::string(mode)=="r");++opens;return {};
}} LittleFS;
bool missing_key=false,healthy=true,bus_idle=true;
namespace rocell_diag {
enum class PairNetworkPhase{New,Other};
struct DiagnosticKeyMaterial{
 bool load(File&){return !missing_key;}
 bool copy_to(uint8_t (&key)[32]){for(int i=0;i<32;++i)key[i]=i;return true;}
 void clear(){}
};
}
bool rocellShoulderReserved=false,rocellDiagnosticOwned=false,rocellPoseReserved=false,
 rocellHoldChallengeAttempted=false,rocellHoldConfigured=false,rocellRecoveryReserved=false;
struct Pair{rocell_diag::PairNetworkPhase value=rocell_diag::PairNetworkPhase::New;auto phase(){return value;}} rocellPairRuntime;
bool rocellHoldHealthy(void*){return healthy;}
bool rocellConfigurationBusInactive(void*){return bus_idle;}
Clock rocellConfiguredClock;Bus st;
char rocellDiagnosticInstance[33]="11111111111111111111111111111111";
unsigned random_calls=0;
void esp_fill_random(void* out,size_t size){memset(out,++random_calls,size);}
struct Platform{size_t free=200000,largest=100000;size_t getFreeHeap(){return free;}size_t getMaxAllocHeap(){return largest;}} ESP;
#include "characterization_board_services.h"
#ifndef ROCELL_BOARD_FIXTURE_ONLY
int main(int argc,char** argv){
 assert(argc==2||argc==3);std::string mode=argv[1];Crypto crypto;
 if(mode=="key")missing_key=true;
 if(mode=="health")healthy=false;
 if(mode=="busy")bus_idle=false;
 if(mode=="heap")ESP.free=1024;
 if(mode=="fragmented")ESP.largest=1024;
 if(mode=="shoulder")rocellShoulderReserved=true;
 if(mode=="diagnostic")rocellDiagnosticOwned=true;
 if(mode=="pose")rocellPoseReserved=true;
 if(mode=="hold")rocellHoldChallengeAttempted=true;
 if(mode=="configured")rocellHoldConfigured=true;
 if(mode=="recovery")rocellRecoveryReserved=true;
 if(mode=="pair")rocellPairRuntime.value=rocell_diag::PairNetworkPhase::Other;
 if(mode=="boot")rocellDiagnosticInstance[0]='z';
 struct Evidence {
   bool operator()(const char*,unsigned,const rocell_diag::ShoulderPreloadPose&,const rocell_diag::CharacterizationResult*){return false;}
   bool release_after_receipt(unsigned){return false;}
 } evidence;
 RocellCharacterizationServices<decltype(evidence)> services{evidence};
 using Controller=rocell_diag::CharacterizationController<Crypto,decltype(services)>;
 auto controller=std::make_unique<Controller>(crypto,services);
 uint16_t bounds[7][2];for(auto& b:bounds){b[0]=0;b[1]=4095;}
 controller->prepare(bounds);
 for(int i=0;i<5;++i){rocellConfiguredClock.tick+=200000;controller->poll();}
 assert(!st.writes);
 bool captured=mode=="success"||mode=="key"||mode=="boot";
 assert(st.reads==(captured?84:0));
 if(mode=="success"){
   assert(controller->session()&&controller->challenge()&&services.owned()&&LittleFS.opens==1);
   uint8_t challenge[224];assert(!controller->publish_challenge(challenge,1));
   size_t count=controller->publish_challenge(challenge,sizeof(challenge));assert(count==224);
   if(argc==3){std::ofstream output(argv[2],std::ios::binary);output.write(reinterpret_cast<const char*>(challenge),count);assert(output.good());}
   assert(!services.reserve());
   rocell_diag::ShoulderPreloadPose pose;
   assert(!services.retain("TEST",0,pose,nullptr)); // Sink refusal propagates.
 }else assert(!controller->session());
 if(captured)assert(rocellShoulderReserved&&rocellDiagnosticOwned); // No failure refund.
 auto reads=st.reads;assert(!controller->prepare(bounds));controller->poll();assert(st.reads==reads);
}
#endif

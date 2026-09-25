#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include <cassert>
#include <fstream>
#include <iterator>
#include <vector>
#include <iostream>
#include <string>
#include "hold_plan_admission.h"
#include "hold_authenticated_runtime.h"
#include "evidence_store.h"
#define main run_hold_owner_cases
#include "test_hold_initialization_owner.cpp"
#undef main
struct GuardedBus:Bus {
 bool* healthy=nullptr;int revoke_at=-1;
 int Read(uint8_t id,uint8_t addr,uint8_t* out,uint8_t width){
  const int result=Bus::Read(id,addr,out,width);
  if(reads==revoke_at)*healthy=false;
  return result;
 }
};
struct RuntimeSink {
 rocell_diag::EvidenceStore<12,4096> backing;
 bool reserve_ok=true,failed=false;int fail_at=-1;
 std::vector<std::string> records;
 bool reserve(size_t count){assert(count==12);return reserve_ok&&backing.reserve(count);}
 bool faulted()const{return failed||backing.faulted();}
 bool publish(const char*,const char* record){
  assert(records.size()<12&&strlen(record)<4608);
  if(int(records.size())==fail_at){failed=true;return false;}
  if(!backing.publish("hold",record))return false;
  records.emplace_back(record);return true;
 }
};
bool healthy_runtime(void* context){return *static_cast<bool*>(context);}
struct Crypto {
 bool hash(const uint8_t* key,const uint8_t* data,size_t length,uint8_t* out){
  BCRYPT_ALG_HANDLE alg=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
  if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,key?BCRYPT_ALG_HANDLE_HMAC_FLAG:0)<0)return false;
  NTSTATUS result=BCryptCreateHash(alg,&hash,nullptr,0,const_cast<PUCHAR>(key),key?32:0,0);
  if(result>=0)result=BCryptHashData(hash,const_cast<PUCHAR>(data),static_cast<ULONG>(length),0);
  if(result>=0)result=BCryptFinishHash(hash,out,32,0);
  if(hash)BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(alg,0);return result>=0;
 }
 bool sha256(const uint8_t* data,size_t length,uint8_t (&out)[32]){return hash(nullptr,data,length,out);}
 bool hmac_sha256(const uint8_t (&key)[32],const uint8_t* data,size_t length,uint8_t (&out)[32]){return hash(key,data,length,out);}
};
#ifndef HOLD_ADMISSION_NO_MAIN
int main(int argc,char** argv){using namespace rocell_diag;
 assert(argc==3);std::ifstream file(argv[1],std::ios::binary);
 std::vector<uint8_t> token((std::istreambuf_iterator<char>(file)),{});
 uint8_t key[32],boot[16],nonce[32];memset(key,'k',32);memset(boot,0x11,16);memset(nonce,0x22,32);
 HoldInitializationPolicy p;const unsigned positions[7]={2048,2390,1727,2723,2041,2042,2051};
 for(size_t i=0;i<7;++i){p.minimum[i]=positions[i]-8;p.maximum[i]=positions[i]+8;}
 Crypto crypto;HoldPlanAdmission admission(key,boot,nonce,1000,10001000);
 const bool ok=admission.consume(token.data(),token.size(),1001,crypto,p,"reviewed-hold");
 assert(ok==(argv[2][0]=='1'));
 assert(!admission.consume(token.data(),token.size(),1002,crypto,p,"reviewed-hold"));
 assert((admission.plan_hash()!=nullptr)==ok);
 for(int scenario=0;scenario<(ok?5:1);++scenario){
  bool healthy=true;GuardedBus bus;bus.healthy=&healthy;Clock clock;clock.tick=1001;RuntimeSink sink;
  if(scenario==1)sink.reserve_ok=false;
  if(scenario==2)sink.fail_at=0;
  if(scenario==3)bus.revoke_at=84; // Lose permission during prewrite scan.
  if(scenario==4)sink.fail_at=7; // Lose terminal publication after successful hold.
  HoldAuthenticatedRuntime<GuardedBus,Clock,RuntimeSink,Crypto> runtime(bus,clock,sink,crypto,
    key,boot,nonce,1000,10001000,p,"reviewed-hold",&healthy_runtime,&healthy);
  const bool started=runtime.start(token.data(),token.size());
  assert(started==(ok&&scenario!=1&&scenario!=2));
  assert(!runtime.start(token.data(),token.size()));
  for(int i=0;i<10;++i){clock.tick+=110000;runtime.poll();}
  if(!ok||scenario==1||scenario==2)assert(bus.reads==0&&bus.writes==0);
  else if(scenario==3)assert(bus.writes==0&&runtime.owner().phase()==HoldPhase::Fault);
  else if(scenario==4)assert(bus.writes==1&&runtime.owner().phase()==HoldPhase::Fault);
  else {assert(runtime.owner().phase()==HoldPhase::Captured&&bus.writes==1&&sink.records.size()==8);
    for(const auto& record:sink.records)std::cout<<record<<"\n";}
  const int reads=bus.reads;runtime.poll();assert(reads==bus.reads);
 }
}
#endif

// Host integration: real envelope/parser/reference conversion, simulated bus.
#define _USE_MATH_DEFINES
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include <cmath>
#include <algorithm>
#include <cassert>
#include <fstream>
#include <iterator>
#include <vector>
#include <cstdio>
#include <cstring>
#include <new>
bool fail_runtime_allocation=false;
void* operator new(size_t size,const std::nothrow_t&) noexcept {
 if(fail_runtime_allocation)return nullptr;
 try{return ::operator new(size);}catch(...){return nullptr;}
}
void operator delete(void* memory,const std::nothrow_t&) noexcept {::operator delete(memory);}
using byte=uint8_t;using u16=uint16_t;using u8=uint8_t;using s16=int16_t;
const int ARM_SERVO_POS_RANGE=4096,ELBOW_SERVO_ID=14;
int goalPos[7]={};
template<class A,class B,class C> int constrain(A n,B low,C high){return std::min<int>(high,std::max<int>(low,n));}
struct SimulatedBus {
 int End=0,Level=1,Error=0,writes=0,reads=0;bool mismatch=false,stationary=false;
 int Read(uint8_t id,uint8_t address,uint8_t* bytes,uint8_t width){
  ++reads;memset(bytes,0,width);
  // An elbow-only write changes only servo 14, not every servo's goal/position.
  const bool commanded=writes&&id==14;
  unsigned value=address==56?(commanded&&!stationary?2132:2128):address==42?(commanded&&!mismatch?2132:0):address==40?1:0;
  bytes[0]=value&255;if(width>1)bytes[1]=value>>8;return width;
 }
 int WritePosEx(int id,int target,int speed,int acc){
  assert(id==14&&target==2132&&speed==20&&acc==1);++writes;return 1;
 }
} st;
#include "pinned_elbow_functions.h"
#include "reference_elbow_admission.h"
#include "startup_authenticated_owner.h"
#include "evidence_store.h"
#include "configured_startup_runtime.h"
// Inert network adapters test runtime initialization/expiry without opening ports.
struct IdleClient{int fd()const{return -1;}void stop(){}};
struct IdleServer{
 bool up=false;IdleServer(uint16_t,int){}void begin(){up=true;}void end(){up=false;}
 explicit operator bool()const{return up;}IdleClient accept(){return {};}
};
struct IdleSocket{
 explicit IdleSocket(IdleClient&){}int receive(uint8_t*,size_t){return -2;}
 int send_once(const uint8_t*,size_t n){return static_cast<int>(n);}void close(){}
};
// Scripted nonblocking connection; all bytes remain in this host process.
struct ScriptNetwork {
 std::vector<uint8_t> request;size_t cursor=0;int accepted=0,replies=0;
 bool pending=true,short_reply=false,eof=false,closed=false;
} network;
struct ScriptClient{int handle=-1;int fd()const{return handle;}void stop(){network.closed=true;}};
struct ScriptServer{
 bool up=false;ScriptServer(uint16_t,int){}void begin(){up=true;}void end(){up=false;}
 explicit operator bool()const{return up;}
 ScriptClient accept(){if(!up||!network.pending)return {};network.pending=false;++network.accepted;return {1};}
};
struct ScriptSocket{
 explicit ScriptSocket(ScriptClient&){}
 int receive(uint8_t* out,size_t capacity){
  if(network.cursor==network.request.size())return network.eof?0:-2;
  size_t count=std::min<size_t>(23,std::min(capacity,network.request.size()-network.cursor));
  memcpy(out,network.request.data()+network.cursor,count);network.cursor+=count;return static_cast<int>(count);
 }
 int send_once(const uint8_t*,size_t n){++network.replies;return static_cast<int>(n)-(network.short_reply?1:0);}
 void close(){network.closed=true;}
};
struct TestKeyFile{
 explicit operator bool()const{return true;}size_t size()const{return 32;}
 size_t read(uint8_t* out,size_t n){memset(out,'k',n);return n;}void close(){}
};
struct NativeCrypto {
 bool hash(const uint8_t* key,const uint8_t* data,size_t length,uint8_t* out){
  BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
  if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,key?BCRYPT_ALG_HANDLE_HMAC_FLAG:0)<0)return false;
  NTSTATUS result=BCryptCreateHash(algorithm,&hash,nullptr,0,const_cast<PUCHAR>(key),key?32:0,0);
  if(result>=0)result=BCryptHashData(hash,const_cast<PUCHAR>(data),static_cast<ULONG>(length),0);
  if(result>=0)result=BCryptFinishHash(hash,out,32,0);
  if(hash)BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(algorithm,0);return result>=0;
 }
 bool sha256(const uint8_t* data,size_t length,uint8_t (&out)[32]){return hash(nullptr,data,length,out);}
 bool hmac_sha256(const uint8_t (&key)[32],const uint8_t* data,size_t length,uint8_t (&out)[32]){return hash(key,data,length,out);}
};
struct TestClock{uint64_t tick=1001;uint64_t now_us(){return ++tick;}};
bool no_fault(void*){return false;}
int main(int argc,char** argv){
 assert(argc==4);std::ifstream file(argv[1],std::ios::binary);
 std::vector<uint8_t> token((std::istreambuf_iterator<char>(file)),{});
 const int expected=atoi(argv[2]);st.mismatch=expected==2;st.stationary=expected==3;
 using namespace rocell_diag;
 uint8_t key[32],boot[16],nonce[32];memset(key,'k',32);memset(boot,0x11,16);memset(nonce,0x22,32);
 std::ifstream config_file(argv[3],std::ios::binary);
 std::string config_bytes((std::istreambuf_iterator<char>(config_file)),{});
 {
  ControllerStartupConfigParser parser;
  assert(parser.parse(config_bytes.data(),config_bytes.size(),"roarm-m3-example20260115-elbow-v1"));
  assert(!parser.parse("{}",2,"roarm-m3-example20260115-elbow-v1")&&!parser.get());
  for(int fault=0;fault<7;++fault){
   JsonDocument bad;assert(!deserializeJson(bad,config_bytes));
   if(fault==0)bad["startup_policy"]["reviewed_mode"]=true;
   if(fault==1)bad["startup_policy"]["policy_id"]="different";
   if(fault==2)bad["startup_policy"]["joints"][0][0]=0;
   if(fault==3)bad["startup_policy"]["minimum_separation_us"]=2000000;
   if(fault==4)bad["startup_policy"]["mode"]="NORMAL";
   if(fault==5)bad["controller_policy"]["challenge_lifetime_us"]=1000;
   if(fault==6)bad["unexpected"]=1;
   std::string serialized;serializeJson(bad,serialized);
   assert(!parser.parse(serialized.data(),serialized.size(),"roarm-m3-example20260115-elbow-v1")&&!parser.get());
  }
  TestKeyFile key_file;DiagnosticKeyMaterial material;assert(material.load(key_file));TestClock runtime_clock;
  ConfiguredStartupRuntime<SimulatedBus,TestClock,IdleServer,IdleClient,IdleSocket,ReferenceElbowAdmission,NativeCrypto> runtime;
  assert(runtime.initialize(st,runtime_clock,config_bytes.data(),config_bytes.size(),
      "roarm-m3-example20260115-elbow-v1",material,boot,nonce,no_fault,nullptr));
  assert(!runtime.initialize(st,runtime_clock,config_bytes.data(),config_bytes.size(),
      "roarm-m3-example20260115-elbow-v1",material,boot,nonce,no_fault,nullptr));
  runtime.poll();assert(runtime.state()==SessionState::Idle&&!runtime.exclusive_work()&&runtime.size()==0);
  runtime_clock.tick=runtime.expires_us();runtime.poll();
  assert(runtime.state()==SessionState::Fault&&!runtime.exclusive_work());
  assert(st.reads==0&&st.writes==0);
  ConfiguredStartupRuntime<SimulatedBus,TestClock,IdleServer,IdleClient,IdleSocket,ReferenceElbowAdmission,NativeCrypto> denied;
  fail_runtime_allocation=true;
  assert(!denied.initialize(st,runtime_clock,config_bytes.data(),config_bytes.size(),
      "roarm-m3-example20260115-elbow-v1",material,boot,nonce,no_fault,nullptr));
  fail_runtime_allocation=false;
  assert(denied.state()==SessionState::Fault&&!strcmp(denied.reason(),"STARTUP_MEMORY_UNAVAILABLE"));
  denied.poll();assert(st.reads==0&&st.writes==0);
  assert(!denied.initialize(st,runtime_clock,config_bytes.data(),config_bytes.size(),
      "roarm-m3-example20260115-elbow-v1",material,boot,nonce,no_fault,nullptr));
 }
 StartupPositionPolicy p={};for(auto& w:p.joints)w={1024,3071};p.drift_tolerance=2;
 p.minimum_separation_us=100000;p.maximum_wait_us=1000000;p.maximum_pair_us=1000;
 p.maximum_scan_us=100000;p.maximum_age_us=100000;
 WholeArmBaselinePolicy normal={};for(auto& w:normal.joints)w={1024,3071};
 normal.tracking_tolerance=2;normal.maximum_pair_us=1000;normal.maximum_scan_us=100000;normal.maximum_age_us=100000;
 TestClock clock;NativeCrypto crypto;EvidenceStore<16,2304> sink;
 ReferenceElbowAdmission converter({1.6,1.9,40,1});goalPos[3]=2222;
 StartupAuthenticatedOwner<SimulatedBus,TestClock,decltype(sink),ReferenceElbowAdmission,NativeCrypto> owner(
  st,clock,sink,converter,crypto,key,boot,nonce,1000,10001000,
  "roarm-m3-example20260115-elbow-v1","test-only",p,0,normal,no_fault,nullptr);
 const bool accepted=owner.start(token.data(),token.size());assert(accepted==(expected!=0));
 assert(st.writes==0&&st.reads==0&&goalPos[3]==2222);
 owner.poll();assert(st.writes==0);clock.tick+=100000;owner.poll();
 for(int i=0;i<3;++i){clock.tick+=1000000;owner.poll();}
 assert(st.writes==(expected?1:0));assert(goalPos[3]==2222);
 assert(owner.state()==(expected==1||expected==3?StartupOwnerState::Captured:StartupOwnerState::Fault));
 if(expected==2)assert(!strcmp(owner.reason(),"TARGET_READBACK_MISMATCH"));
 assert(!owner.start(token.data(),token.size()));owner.poll();assert(st.writes==(expected?1:0));
 for(size_t i=0;i<sink.size();++i){const auto* r=sink.get(i);printf("%s\t%s\n",r->kind,r->json);}
 // Exercise the same authenticated bytes through configuration -> listener ->
 // HTTP framing -> owner -> evidence, not only direct owner.start().
 for(int fault=0;fault<4;++fault){
  st.reads=st.writes=0;network={};network.short_reply=fault==1;network.eof=fault==2;
  const std::string header="POST /rocell/diagnostics/start HTTP/1.1\r\nHost: test\r\nContent-Length: "+
    std::to_string(token.size())+"\r\nContent-Type: application/octet-stream\r\nConnection: close\r\n\r\n";
  network.request.assign(header.begin(),header.end());network.request.insert(network.request.end(),token.begin(),token.end());
  if(fault==3)network.request.push_back('!');
  TestClock socket_clock;socket_clock.tick=999;TestKeyFile key_file;DiagnosticKeyMaterial material;
  assert(material.load(key_file));
  ConfiguredStartupRuntime<SimulatedBus,TestClock,ScriptServer,ScriptClient,ScriptSocket,ReferenceElbowAdmission,NativeCrypto> runtime;
  assert(runtime.initialize(st,socket_clock,config_bytes.data(),config_bytes.size(),
    "roarm-m3-example20260115-elbow-v1",material,boot,nonce,no_fault,nullptr));
  assert(runtime.issued_us()==1000&&runtime.expires_us()==10001000);
  for(size_t i=0;i<network.request.size()/23+4&&!network.closed;++i){
   runtime.poll();assert(st.reads==0&&st.writes==0);
  }
  assert(network.closed&&network.accepted==1&&network.replies==1);
  runtime.poll();assert(st.writes==0);
  socket_clock.tick+=100000;runtime.poll();
  for(int i=0;i<3;++i){socket_clock.tick+=1000000;runtime.poll();}
  const bool executes=expected!=0&&fault==0;
  assert(st.writes==(executes?1:0));
  assert(runtime.state()==(executes&&expected!=2?SessionState::Captured:SessionState::Fault));
  if(!executes)assert(st.reads==0);
  assert(!runtime.exclusive_work());
  network.pending=true;runtime.poll();assert(network.accepted==1); // Never re-arm.
  if(executes&&expected==1){
   const int writes_before=st.writes;
   StartupPositionBaseline startup_again(p);startup_again.poll(st,socket_clock);
   assert(startup_again.state()==StartupPositionState::Fault);
   assert(!strcmp(startup_again.reason(),"STARTUP_GOAL_NOT_ZERO"));
   WholeArmBaseline normal_again(normal);
   assert(!normal_again.check(st,socket_clock));
   assert(!strcmp(normal_again.reason(),"WHOLE_ARM_OUTSIDE_WINDOW"));
   assert(st.writes==writes_before); // Neither refusal dispatches recovery motion.
  }
 }
}

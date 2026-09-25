#define _USE_MATH_DEFINES
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include <cmath>
#include <algorithm>
#include <fstream>
#include <iterator>
#include <string>
#include <cassert>
#include <cstdint>
using byte=uint8_t;using u16=uint16_t;using u8=uint8_t;using s16=int16_t;
const int ARM_SERVO_POS_RANGE=4096,ELBOW_SERVO_ID=14;
int goalPos[7]={};
template<class A,class B,class C> int constrain(A n,B low,C high){return std::min<int>(high,std::max<int>(low,n));}
struct Bus {
  int writes=0,reads=0,End=0,Level=1,Error=0,bad_id=0,result=1,position=2132;
  int WritePosEx(int,int target,int,int){++writes;if(result==1)position=target;return result;}
  int Read(uint8_t id,uint8_t,uint8_t* data,uint8_t width){
    ++reads;if(id==bad_id)return 0;data[0]=position&255;data[1]=position>>8;return width;
  }
} st;
#include "pinned_elbow_functions.h"
#include "reference_elbow_admission.h"
#include "start_plan_structure.h"
#include "authorized_start.h"
#include "evidence_store.h"
#include "admitted_session.h"
#include "authenticated_diagnostic_owner.h"
#include "diagnostic_status_json.h"
#include "start_request_body.h"
#include "start_http_request.h"
#include "start_socket_session.h"
#include "start_listener.h"
#include "configured_diagnostic_runtime.h"
struct Crypto {
  bool digest(const uint8_t* data,size_t length,uint8_t (&out)[32],const uint8_t* key=nullptr) {
    BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,key?BCRYPT_ALG_HANDLE_HMAC_FLAG:0)<0)return false;
    NTSTATUS result=BCryptCreateHash(algorithm,&hash,nullptr,0,const_cast<PUCHAR>(key),key?32:0,0);
    if(result>=0)result=BCryptHashData(hash,const_cast<PUCHAR>(data),static_cast<ULONG>(length),0);
    if(result>=0)result=BCryptFinishHash(hash,out,32,0);
    if(hash)BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(algorithm,0);return result>=0;
  }
  bool sha256(const uint8_t* data,size_t length,uint8_t (&out)[32]){return digest(data,length,out);}
  bool hmac_sha256(const uint8_t (&key)[32],const uint8_t* data,size_t length,uint8_t (&out)[32]){return digest(data,length,out,key);}
};
struct Clock {uint64_t tick=1001;uint64_t now_us(){return tick++;}};
struct Sink {
  rocell_diag::EvidenceStore<16> store;bool fail=false;
  int mode=0;Clock* clock=nullptr;bool* fault=nullptr;
  bool reserve(size_t count){return store.reserve(count);}
  bool faulted() const{return store.faulted();}
  bool publish(const char* kind,const char* body){
    if(mode==12 && !strcmp(kind,"converted"))clock->tick+=2000;
    if(mode==13 && !strcmp(kind,"converted"))*fault=true;
    if(mode==14 && !strcmp(kind,"baseline"))return false;
    return !fail && store.publish(kind,body);
  }
};
bool test_fault(void* context){return *static_cast<bool*>(context);}
struct Socket {
  int descriptor=-1;int fd() const{return descriptor;}
  std::string bytes,reply;size_t offset=0;int mode=50,reads=0,sends=0,closes=0;
  int receive(uint8_t* output,size_t capacity){
    ++reads;
    if(mode==52)return 0;if(mode==53)return -1;if(mode==54)return -2;
    if(offset==bytes.size())return -2;
    const size_t n=std::min<size_t>(37,std::min(capacity,bytes.size()-offset));
    memcpy(output,bytes.data()+offset,n);offset+=n;return static_cast<int>(n);
  }
  int send_once(const uint8_t* data,size_t size){
    ++sends;reply.assign(reinterpret_cast<const char*>(data),size);
    return mode==51?0:mode==55?static_cast<int>(size)-1:mode==56?-2:static_cast<int>(size);
  }
  void close(){++closes;}
  void stop(){close();}
};
struct Server {
  static Socket queued;static bool reject_next;
  Server()=default;
  Server(uint16_t port,uint8_t clients){assert(port==8081 && clients==1);pending=queued;reject=reject_next;}
  Socket pending;bool up=false,reject=false;int starts=0,ends=0,accepts=0;
  void begin(){++starts;up=!reject;}
  explicit operator bool() const{return up;}
  Socket accept(){++accepts;Socket result=pending;pending.descriptor=-1;return result;}
  void end(){++ends;up=false;}
};
Socket Server::queued;bool Server::reject_next=false;
struct SocketAdapter {
  Socket& client;explicit SocketAdapter(Socket& c):client(c) {}
  int receive(uint8_t* data,size_t size){return client.receive(data,size);}
  int send_once(const uint8_t* data,size_t size){return client.send_once(data,size);}
  void close(){client.close();}
};
struct KeyFile {
  explicit operator bool() const{return true;}size_t size() const{return 32;}
  int read(uint8_t* bytes,size_t n){assert(n==32);for(size_t i=0;i<n;++i)bytes[i]=31-i;return 32;}
  void close(){}
};
struct Admission {
  Sink& sink;Clock& clock;int mode,calls=0;
  bool check(const rocell_diag::BoundStartRequest& request){
    ++calls;assert(sink.store.size()==1 && request.wire_count==2132);
    if(request.has_whole_arm)assert(request.whole_arm.joints[0].minimum==1900);
    if(mode==2)clock.tick=11000;
    return mode!=1;
  }
};
struct Starter {
  Admission& admission;int mode,calls=0;
  bool start(const rocell_diag::BoundStartRequest& request){
    ++calls;assert(admission.calls==1 && request.wire_count==2132 && request.samples==3);
    return mode!=4;
  }
};
int main(int argc,char** argv){
  assert(argc==3 || argc==4);std::ifstream stream(argv[1],std::ios::binary);
  std::string bytes((std::istreambuf_iterator<char>(stream)),{});
  rocell_diag::StartPlanStructure parser;Crypto crypto;
  rocell_diag::ReferenceElbowAdmission converter({1.6,1.9,40,1});
  goalPos[3]=2222;
  if(argc==4){
    int mode=atoi(argv[3]);uint8_t key[32],boot[16],nonce[32];
    for(int i=0;i<32;++i){key[i]=i;nonce[i]=0x22;}for(auto& b:boot)b=0x11;
    rocell_diag::WholeArmBaselinePolicy approved={};
    for(auto& window:approved.joints)window={1900,2200};
    approved.tracking_tolerance=2;approved.maximum_pair_us=100;
    approved.maximum_scan_us=1000;approved.maximum_age_us=1000;
    rocell_diag::AuthorizedStart owner(key,boot,nonce,1000,11000,"test-reference",mode==5?nullptr:&approved);
    if(mode==6)approved.joints[0].minimum=0; // Constructor must own its policy copy.
    Clock clock;Sink sink;sink.fail=mode==3;Admission admission{sink,clock,mode,0};Starter starter{admission,mode,0};
    if(mode>=10){
      st.position=2128; // Known pre-target offset; simulated write changes feedback.
      bool fault=false;sink.mode=mode;sink.clock=&clock;sink.fault=&fault;
      if(mode==11)st.bad_id=13;if(mode==15)st.result=0;
      rocell_diag::AuthenticatedDiagnosticOwner<Bus,Clock,Sink,rocell_diag::ReferenceElbowAdmission,Crypto> integrated(
          st,clock,sink,converter,crypto,key,boot,nonce,1000,11000,"test-reference",approved,test_fault,&fault);
      assert(integrated.state()==rocell_diag::SessionState::Idle && !integrated.owned());
      assert(!integrated.sample() && st.reads==0 && st.writes==0);
      if(mode>=70){
        std::string policy=R"({"challenge_lifetime_us":10000,"conversion_version":"test-reference","elbow_bounds":{"maximum_acceleration":1,"maximum_rad":1.9,"maximum_speed":40,"minimum_rad":1.6},"policy_id":"inert-only","schema":"rocell.controller_diagnostics.v1","start_port":8081,"whole_arm_policy":{"joints":[[1900,2200],[1900,2200],[1900,2200],[1900,2200],[1900,2200],[1900,2200],[1900,2200]],"maximum_age_us":1000,"maximum_pair_us":100,"maximum_scan_us":1000,"tracking_tolerance":2}})";
        rocell_diag::DiagnosticKeyMaterial material;KeyFile key_file;
        if(mode!=72)assert(material.load(key_file));
        if(mode==71)policy="{}";if(mode==74)fault=true;
        Server::queued.bytes=bytes;Server::queued.descriptor=7;Server::reject_next=mode==73;
        rocell_diag::ConfiguredDiagnosticRuntime<Bus,Clock,Server,Socket,SocketAdapter,
            rocell_diag::ReferenceElbowAdmission,Crypto> runtime;
        assert(runtime.state()==rocell_diag::SessionState::Idle && runtime.size()==0 && !runtime.get(0));
        assert(runtime.initialize(st,clock,policy.data(),policy.size(),"test-reference",material,boot,nonce,test_fault,&fault)==(mode==70));
        material.clear();policy.clear(); // All needed data must be owned now.
        assert(!runtime.initialize(st,clock,nullptr,0,"test-reference",material,boot,nonce,test_fault,&fault));
        if(mode==70){
          assert(runtime.issued_us()==1001 && runtime.expires_us()==11001);
          for(int i=0;i<1000 && runtime.state()!=rocell_diag::SessionState::Captured && runtime.state()!=rocell_diag::SessionState::Fault;++i){
            if(st.writes)clock.tick+=1000010;runtime.poll();
          }
          assert(runtime.state()==rocell_diag::SessionState::Captured && st.writes==1 && st.reads==22);
          assert(runtime.size()==11 && runtime.get(10));
        }else assert(runtime.state()==rocell_diag::SessionState::Fault && st.writes==0 && st.reads==0);
        const int reads=st.reads;runtime.poll();assert(st.reads==reads);
        char status[512];assert(rocell_diag::diagnostic_status_json(runtime,runtime,runtime.instance(),status,sizeof(status),true));
        puts(status);for(size_t i=0;i<runtime.size();++i)puts(runtime.get(i)->json);
        return 0;
      }
      if(mode>=60){
        Socket socket;Server server;
        server.pending.bytes=bytes;server.pending.descriptor=7;
        server.pending.mode=mode==64?51:50;
        if(mode==61)server.reject=true;
        if(mode==62 || mode==63)server.pending.descriptor=-1;
        rocell_diag::StartSocketSession<decltype(integrated),Clock,Socket> connection(integrated,clock,socket);
        rocell_diag::StartListener<Server,Socket,decltype(connection),decltype(integrated),Clock> listener(
            server,socket,connection,integrated,clock,11000);
        assert(listener.begin()==(mode!=61));assert(!listener.begin());
        if(mode==62)clock.tick=11000;
        if(mode==63)clock.tick=1000;
        for(int i=0;i<1000 && listener.state()!=rocell_diag::ListenerState::Finished &&
            listener.state()!=rocell_diag::ListenerState::Fault;++i){
          if(!connection.active() && integrated.state()==rocell_diag::SessionState::Sampling)clock.tick+=1000010;
          listener.poll();
        }
        assert(listener.state()==(mode==60?rocell_diag::ListenerState::Finished:rocell_diag::ListenerState::Fault));
        assert(st.writes==((mode==60||mode==64)?1:0));
        if(mode==60)assert(st.reads==22);
        else if(mode!=64)assert(st.reads==0);
        assert(!server.up && server.starts==1 && server.ends==1);
        const int before=st.reads,accepted=server.accepts;
        listener.poll();assert(!listener.begin());
        assert(st.reads==before && server.accepts==accepted);
        puts(listener.reason());return 0;
      }
      if(mode>=50){
        Socket socket;socket.bytes=bytes;socket.mode=mode;
        rocell_diag::StartSocketSession<decltype(integrated),Clock,Socket> connection(integrated,clock,socket);
        assert(connection.begin() && !connection.begin());
        for(int i=0;connection.active() && i<1000;++i){
          if(mode==54)clock.tick+=3000001;
          connection.poll();
        }
        assert(!connection.active() && socket.closes==1 && socket.sends==1);
        assert(st.writes==((mode==50 || mode==51 || mode==55 || mode==56)?1:0));
        if(mode==50)assert(integrated.state()==rocell_diag::SessionState::Sampling);
        else {assert(integrated.state()==rocell_diag::SessionState::Fault);
          const int before=st.reads;assert(!integrated.sample() && st.reads==before);}
        const int before=socket.reads;assert(!connection.poll() && !connection.begin());
        assert(socket.reads==before && socket.sends==1 && socket.closes==1);
        puts(connection.reason());return 0;
      }
      if(mode>=40){
        rocell_diag::StartHttpRequest<decltype(integrated)> request(integrated);
        assert(request.begin(1001,1000));assert(!request.begin(1001,1000));
        const auto* data=reinterpret_cast<const uint8_t*>(bytes.data());
        bool accepted=true;const size_t chunk=mode==41?1:bytes.size();
        for(size_t i=0;accepted && i<bytes.size();i+=chunk)
          accepted=request.feed(data+i,std::min(chunk,bytes.size()-i),1002);
        assert(st.reads==0 && st.writes==0);
        if(mode==42){request.abort();accepted=false;}
        if(mode==43){assert(!request.poll(2001));accepted=false;}
        if(mode==44){assert(!request.poll(1001));accepted=false;}
        bool started=accepted && request.finish(1003);
        assert(started==(strcmp(argv[2],"yes")==0));
        assert(st.writes==(started?1:0));assert(started || st.reads==0);
        const int reads=st.reads;
        assert(!request.finish(1004) && !request.feed(data,1,1004) && !request.begin(1004));
        assert(st.reads==reads && st.writes==(started?1:0));
        puts(request.reason());return 0;
      }
      if(mode>=20){
        rocell_diag::StartRequestBody<decltype(integrated)> receiver(integrated);
        const auto* data=reinterpret_cast<const uint8_t*>(bytes.data());
        const size_t size=bytes.size();
        if(mode>=27){
          const size_t length=mode==27?decltype(receiver)::MinimumBytes-1:
              mode==28?decltype(receiver)::MaximumBytes+1:size;
          const uint64_t now=mode==31?INT64_MAX:1001;
          const uint64_t budget=mode==29?0:mode==30?3000001:1000;
          assert(!receiver.begin(length,now,budget));
          assert(!receiver.begin(size,1001,1000));
          assert(integrated.state()==rocell_diag::SessionState::Fault && st.reads==0 && st.writes==0);
          puts(receiver.reason());return 0;
        }
        assert(receiver.begin(size,1001,1000));
        assert(!receiver.begin(size,1001,1000));
        bool started=false;
        if(mode==20){
          for(size_t i=0;i<size;i+=37){assert(receiver.append(data+i,std::min<size_t>(37,size-i),1002));}
          assert(st.reads==0 && st.writes==0);
          started=receiver.finish(1003);assert(started);
        }else if(mode==21){assert(receiver.append(data,size-1,1002));assert(!receiver.finish(1003));}
        else if(mode==22){assert(!receiver.append(data,size+1,1002));}
        else if(mode==23){assert(!receiver.append(data,size,2001));}
        else if(mode==24){assert(receiver.append(data,1,1002));assert(!receiver.append(data+1,size-1,1001));}
        else if(mode==25){assert(receiver.append(data,1,1002));receiver.abort();}
        else if(mode==26){assert(receiver.append(data,size,1002));assert(!receiver.finish(2001));}
        assert(st.writes==(started?1:0));assert(started || st.reads==0);
        const int before=st.reads;
        assert(!receiver.finish(1004) && !receiver.append(data,1,1004) && !receiver.begin(size,1004,1000));
        assert(st.reads==before);
        assert(integrated.state()==(started?rocell_diag::SessionState::Sampling:rocell_diag::SessionState::Fault));
        printf("%s\n",receiver.reason());return 0;
      }
      bool ok=integrated.start(reinterpret_cast<const uint8_t*>(bytes.data()),bytes.size());
      assert(ok==(mode==10 || mode>=16));assert(integrated.owned());
      if(ok){
        if(mode==16)integrated.export_failed();
        if(mode==17)integrated.interference();
        if(mode==18)fault=true;
        if(mode==19)assert(!sink.reserve(99));
        if(mode==10){for(int i=0;i<3;++i){clock.tick+=1000010;assert(integrated.sample());}
          assert(integrated.state()==rocell_diag::SessionState::Captured && st.reads==22);}
        else {const int before=st.reads;clock.tick+=1000010;assert(!integrated.sample());assert(st.reads==before);}
      }
      if(mode!=10){assert(integrated.state()==rocell_diag::SessionState::Fault);
        const char* expected=mode==11?"ADMISSION_REJECTED":mode==12||mode==13?"WRITE_NOT_ATTEMPTED":
          mode==14?"ADMISSION_REJECTED":mode==15?"WRITE_NOT_VERIFIED":mode==17?"INTERFERING_COMMAND":
          mode==18?"OWNER_FAULT":"EVIDENCE_FAILURE";
        assert(!strcmp(integrated.reason(),expected));
      }
      assert(st.writes==((mode==10||mode>=15)?1:0));
      if(mode==11)assert(st.reads==6);
      const int reads=st.reads,writes=st.writes;
      assert(!integrated.start(reinterpret_cast<const uint8_t*>(bytes.data()),bytes.size()));
      assert(!integrated.sample());
      assert(st.reads==reads && st.writes==writes && goalPos[3]==2222);
      char status[512],tiny[8];
      assert(!rocell_diag::diagnostic_status_json(integrated,sink.store,"11111111111111111111111111111111",tiny,sizeof(tiny)) && !tiny[0]);
      assert(rocell_diag::diagnostic_status_json(integrated,sink.store,"11111111111111111111111111111111",status,sizeof(status)));
      puts(status);
      for(size_t i=0;i<sink.store.size();++i)puts(sink.store.get(i)->json);
      return 0;
    }
    bool result=owner.start(reinterpret_cast<const uint8_t*>(bytes.data()),bytes.size(),clock,crypto,converter,sink,admission,starter);
    assert(result==(strcmp(argv[2],"yes")==0));
    assert(st.writes==0 && goalPos[3]==2222);
    printf("%s %d %d\n",owner.reason(),admission.calls,starter.calls);
    if(sink.store.size())puts(sink.store.get(0)->json);
    const int before=starter.calls;
    assert(!owner.start(reinterpret_cast<const uint8_t*>(bytes.data()),bytes.size(),clock,crypto,converter,sink,admission,starter));
    assert(starter.calls==before);return 0;
  }
  const bool ok=parser.parse(bytes.data(),bytes.size(),"11111111111111111111111111111111","test-reference") &&
      parser.bind_payload(crypto,converter);
  assert(ok==(strcmp(argv[2],"yes")==0));assert(st.writes==0 && goalPos[3]==2222);
  if(ok)fwrite(parser.original_payload(),1,parser.original_length(),stdout);
  else assert(!parser.original_payload() && parser.original_length()==0);
  assert(!parser.parse("{}",2,"11111111111111111111111111111111","test-reference"));
  assert(!parser.original_payload() && !parser.bind_payload(crypto,converter));
}

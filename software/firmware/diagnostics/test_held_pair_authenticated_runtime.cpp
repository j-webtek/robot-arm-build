#define HOLD_ADMISSION_NO_MAIN
#include "test_hold_plan_admission.cpp"
#include "held_pair_authenticated_runtime.h"
#include "held_pair_transport_json.h"
#include "held_pair_listener_owner.h"
#include "start_socket_session.h"
#include <memory>
struct MotionBus:Bus{
  bool track_target=true;
  int WritePosEx(uint8_t id,int16_t target,uint16_t speed,uint8_t acceleration){
    assert(id==14&&speed==20&&acceleration==1);++writes;
    goal[3]=target;if(track_target)position[3]=target;torque[3]=1;Error=0;return 1;
  }
};
std::vector<uint8_t> read_token(const char* path){
  std::ifstream file(path,std::ios::binary);
  return std::vector<uint8_t>((std::istreambuf_iterator<char>(file)),{});
}
struct PairTestSocket {
  std::vector<uint8_t> request;size_t offset=0;bool closed=false,short_reply=false;
  int receive(uint8_t* out,size_t maximum){
    if(offset==request.size())return -2;
    size_t n=std::min(maximum,request.size()-offset);memcpy(out,request.data()+offset,n);offset+=n;return int(n);
  }
  int send_once(const uint8_t*,size_t n){return int(n)-(short_reply?1:0);}
  void close(){closed=true;}
};
template<class Runtime,class Operation>
bool socket_admit(Runtime& runtime,Operation& operation,Clock& clock,
                  const std::vector<uint8_t>& token,bool returning,bool short_reply=false){
  using Owner=HeldPairListenerOwner<Runtime,Operation>;
  Owner owner(runtime,operation,returning);PairTestSocket socket;
  socket.short_reply=short_reply;
  std::string header="POST /rocell/diagnostics/start HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/octet-stream\r\nConnection: close\r\nContent-Length: "+std::to_string(token.size())+"\r\n\r\n";
  socket.request.assign(header.begin(),header.end());socket.request.insert(socket.request.end(),token.begin(),token.end());
  auto connection=std::unique_ptr<StartSocketSession<Owner,Clock,PairTestSocket>>(
      new StartSocketSession<Owner,Clock,PairTestSocket>(owner,clock,socket));
  assert(connection->begin());
  for(int i=0;i<30&&connection->active();++i)connection->poll();
  assert(!connection->active()&&socket.closed&&owner.owned());
  assert(!connection->begin());
  return owner.state()!=SessionState::Fault;
}
int main(int argc,char** argv){
  assert(argc==6||argc==7);const bool socket_mode=argc==7;
  MotionBus bus;Clock clock;Crypto crypto;bool healthy=true;
  if(argc==7&&!strcmp(argv[6],"socket-powered")){
    bus.automatic=false;bus.torque[3]=1;bus.goal[3]=2724;
  }
  auto p=policy();clock.tick=1001;
  const char* hold_id="verified-hold";
  unsigned expected_anchor=2723;
#ifdef OBSERVED_POSE_PLUS10
  // Exact proposed public policy; recovery is separately exercised by the core
  // fixture. Here the signed ordinary hold starts at a reconciled enabled pose.
  const unsigned observed[7]={2047,2487,1629,2899,2035,2041,2054};
  for(int i=0;i<7;++i){bus.position[i]=observed[i];p.minimum[i]=observed[i]-2;p.maximum[i]=observed[i]+2;}
  p.minimum[3]=2893;p.maximum[3]=2909;p.permit_explicit_enable=false;
  bus.automatic=false;bus.torque[3]=1;bus.goal[3]=2899;
  hold_id="observed-pose-elbow-hold-v1";expected_anchor=2899;
#endif
  const bool positive12=argc==7&&!strcmp(argv[6],"positive12");
  // Test-only translated encoder window; production limits are not modified.
  if(positive12){p.minimum[3]=2719;p.maximum[3]=2735;}
  uint8_t key[32],boot[16],nonce[32];memset(key,'k',32);memset(boot,0x11,16);memset(nonce,0x22,32);
  uint8_t hold_nonce[32];memset(hold_nonce,0x44,32);
  using HoldRuntime=HoldAuthenticatedRuntime<MotionBus,Clock,EvidenceStore<12,4096>,Crypto>;
  auto hold_store=std::unique_ptr<EvidenceStore<12,4096>>(new EvidenceStore<12,4096>());
  auto held=std::unique_ptr<HoldRuntime>(new HoldRuntime(bus,clock,*hold_store,crypto,
      key,boot,hold_nonce,1000,10001000,p,hold_id,healthy_runtime,&healthy));
  auto hold_token=read_token(argv[5]);assert(held->start(hold_token.data(),hold_token.size()));
  for(int i=0;i<10;++i){clock.tick+=110000;held->poll();}
  assert(held->owner().phase()==HoldPhase::Captured&&bus.writes==1);
  // Test-only archive retained before destroying the old graph. Allows host
  // integration to replay the actual hold-to-pair evidence chain end to end.
  std::vector<std::pair<std::string,std::string>> hold_records;
  for(size_t i=0;i<hold_store->size();++i){const auto* record=hold_store->get(i);
    assert(record);hold_records.emplace_back(record->kind,record->json);}
  VerifiedHoldHandoff handoff;assert(held->take_handoff(handoff));
  VerifiedHoldHandoff duplicate;assert(!held->take_handoff(duplicate));
  std::string hold_hash=handoff.plan_hash();const char* boot_text="11111111111111111111111111111111";
  char policy_bytes[1536];uint8_t policy_digest[32];char policy_hash[65];
  assert(hold_policy_json(p,policy_bytes,sizeof(policy_bytes)));
  assert(crypto.sha256(reinterpret_cast<const uint8_t*>(policy_bytes),strlen(policy_bytes),policy_digest));
  for(size_t i=0;i<32;++i)sprintf(policy_hash+2*i,"%02x",policy_digest[i]);
  const char* mode=socket_mode?argv[6]:"direct";
  if(!strcmp(mode,"nonarrival"))bus.track_target=false;
  const bool interactive=!strcmp(mode,"interactive");
  if(interactive){
    JsonDocument meta;auto records=meta["hold_records"].to<JsonArray>();
    for(const auto& record:hold_records){auto entry=records.add<JsonObject>();
      entry["kind"]=record.first;entry["raw_json"]=record.second;}
    serializeJson(meta,std::cout);std::cout<<std::endl;
  }
  if(!strcmp(mode,"handoff_boot"))assert(!handoff.consume("33333333333333333333333333333333",hold_hash.c_str(),policy_hash));
  if(!strcmp(mode,"handoff_plan"))assert(!handoff.consume(boot_text,std::string(64,'e').c_str(),policy_hash));
  if(!strcmp(mode,"handoff_policy"))assert(!handoff.consume(boot_text,hold_hash.c_str(),std::string(64,'e').c_str()));
  if(!strcmp(mode,"handoff_used"))assert(handoff.consume(boot_text,hold_hash.c_str(),policy_hash));
  VerifiedHoldHandoff& selected_handoff=!strcmp(mode,"handoff_empty")?duplicate:handoff;
  held.reset();hold_store.reset(); // Release the old graph BEFORE allocating pair.
  using Runtime=HeldPairAuthenticatedRuntime<MotionBus,Clock,Crypto>;
  const char* forward_id=positive12?"elbow-plus12-forward":"forward";
  const char* return_id=positive12?"elbow-plus12-return":"return";
  int offset=positive12?12:6;
#ifdef OBSERVED_POSE_PLUS10
  forward_id="observed-pose-plus10-forward";return_id="observed-pose-plus10-return";offset=10;
#endif
  auto runtime=std::unique_ptr<Runtime>(new Runtime(bus,clock,crypto,p,boot_text,
      hold_hash.c_str(),forward_id,return_id,offset,2,healthy_runtime,&healthy));
  HeldPairPlanAdmission gate(key,boot,nonce,1000,10001000);
  std::string start_path=argv[1];
  if(interactive)assert(bool(std::getline(std::cin,start_path)));
  auto start=read_token(start_path.c_str());const int reads=bus.reads;
  HeldPairInitialOperation<Runtime> initial_operation{*runtime,gate,selected_handoff};
  bool accepted=socket_mode?socket_admit(*runtime,initial_operation,clock,start,false,!strcmp(argv[6],"shortstart")):
      runtime->start(gate,start.data(),start.size(),selected_handoff);
  assert(accepted==(argv[3][0]=='1'));
  assert(!runtime->start(gate,start.data(),start.size(),handoff));
  assert(bus.reads==reads&&bus.writes==1); // Admission is non-actuating.
  for(int i=0;i<30;++i){clock.tick+=110000;runtime->poll();}
  if(!accepted){assert(runtime->phase()==HeldPairPhase::Stopped&&bus.writes==1);return 0;}
  if(!strcmp(mode,"nonarrival")){
    assert(runtime->phase()==HeldPairPhase::Stopped&&bus.writes==2);
    assert(!strcmp(runtime->reason(),"LEG_NOT_ARRIVED"));
    const int reads=bus.reads;const size_t records=runtime->evidence().size();
    runtime->interference();runtime->interference();runtime->poll();
    assert(!strcmp(runtime->reason(),"LEG_NOT_ARRIVED"));
    assert(bus.reads==reads&&bus.writes==2&&runtime->evidence().size()==records);
    std::cout<<"NONARRIVAL_REASON_PRESERVED\n";return 0;
  }
  assert(runtime->phase()==HeldPairPhase::AwaitingExport&&bus.writes==2);
  if(!strcmp(argv[2],"-")||interactive){
    JsonDocument meta;meta["session_sha256"]=runtime->session_hash();
    meta["forward_plan_sha256"]=runtime->forward_hash();
    meta["forward_plan_json"]=runtime->forward_plan();meta["runtime_bytes"]=sizeof(Runtime);
    auto held_records=meta["hold_records"].to<JsonArray>();
    for(const auto& record:hold_records){auto entry=held_records.add<JsonObject>();
      entry["kind"]=record.first;entry["raw_json"]=record.second;}
    std::vector<char> wire(9216);
    assert(held_pair_status_json(*runtime,wire.data(),1024));
    meta["transport_status_json"]=std::string(wire.data());
    auto records=meta["transport_records"].to<JsonArray>();
    for(size_t i=0;i<runtime->evidence().size();++i){
      assert(held_pair_record_json(*runtime,i,wire.data(),wire.size()));
      records.add(std::string(wire.data()));
    }
    const int unchanged=bus.reads;
    assert(!held_pair_record_json(*runtime,34,wire.data(),wire.size()));
    assert(bus.reads==unchanged&&bus.writes==2);
    serializeJson(meta,std::cout);std::cout<<std::endl;
    if(!interactive){for(size_t i=0;i<runtime->evidence().size();++i){auto* r=runtime->evidence().get(i);
      std::cout<<r->kind<<"\t"<<r->json<<"\n";}
      return 0;
    }
  }
  const int before=bus.reads;memset(nonce,0x33,32);
  std::string back_path=argv[2];
  if(interactive)assert(bool(std::getline(std::cin,back_path)));
  HeldReturnAdmission back_gate(key,boot,nonce,2000,10002000);auto back=read_token(back_path.c_str());
  HeldPairReturnOperation<Runtime> return_operation{*runtime,back_gate};
  bool returned=socket_mode?socket_admit(*runtime,return_operation,clock,back,true,!strcmp(argv[6],"shortreturn")):
      runtime->admit_return(back_gate,back.data(),back.size());
  assert(returned==(argv[4][0]=='1'));
  assert(!runtime->admit_return(back_gate,back.data(),back.size()));
  assert(bus.reads==before&&bus.writes==2);
  for(int i=0;i<30;++i){clock.tick+=110000;runtime->poll();}
  if(returned){
    assert(runtime->phase()==HeldPairPhase::Complete&&bus.writes==3&&bus.position[3]==expected_anchor);
    assert(runtime->evidence().size()==7&&runtime->return_plan());
    JsonDocument meta;std::vector<char> wire(9216);
    assert(held_pair_status_json(*runtime,wire.data(),1024));
    meta["transport_status_json"]=std::string(wire.data());
    auto records=meta["transport_records"].to<JsonArray>();
    for(size_t i=0;i<runtime->evidence().size();++i){
      assert(held_pair_record_json(*runtime,i,wire.data(),wire.size()));
      records.add(std::string(wire.data()));
    }
    serializeJson(meta,std::cout);std::cout<<std::endl;
  }else assert(runtime->phase()==HeldPairPhase::Stopped&&bus.writes==2);
  return 0;
}

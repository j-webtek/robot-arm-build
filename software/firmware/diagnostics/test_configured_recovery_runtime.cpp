#define CONFIGURED_HOLD_NO_MAIN
#include "test_configured_hold_runtime.cpp"
#undef CONFIGURED_HOLD_NO_MAIN
int main(int argc,char** argv){
  assert(argc==2);std::ifstream file(argv[1],std::ios::binary);
  std::vector<uint8_t> token((std::istreambuf_iterator<char>(file)),{});
  uint8_t key[32],boot[16],nonce[32];memset(key,'k',32);memset(boot,0x11,16);memset(nonce,0x22,32);
  using Recovery=ConfiguredHoldRuntime<GuardedBus,Clock,ConfigServer,Client,Socket,Crypto,true>;
  for(int scenario=0;scenario<8;++scenario){
    Network net;current_network=&net;GuardedBus bus;Clock clock;clock.tick=1001;Crypto crypto;
    bool healthy=true;bus.healthy=&healthy;bus.automatic=false;bus.torque[3]=1;bus.goal[3]=2728;
    configured_allocations=0;fail_configured_allocation=(scenario==1||scenario==2)?scenario:0;
    fail_configured_listener=scenario==3;
    std::string header="POST /rocell/diagnostics/start HTTP/1.1\r\nHost: test\r\nConnection: close\r\nContent-Type: application/octet-stream\r\nContent-Length: "+
      std::to_string(token.size())+"\r\n\r\n";
    net.request.assign(header.begin(),header.end());net.request.insert(net.request.end(),token.begin(),token.end());
    Recovery runtime;
    if(scenario==7){
      assert(!runtime.initialize_config(bus,clock,crypto,key,boot,nonce,1000,10001000,
          "{}",2,healthy_runtime,&healthy));
      assert(!strcmp(runtime.reason(),"RECOVERY_EXPLICIT_POLICY_REQUIRED"));
    }else{
      assert(runtime.initialize(bus,clock,crypto,key,boot,nonce,1000,10001000,8081,
          policy(),"reviewed-recovery",healthy_runtime,&healthy)==(scenario==0||scenario>=4));
    }
    fail_configured_allocation=0;fail_configured_listener=false;
    assert(!runtime.initialize(bus,clock,crypto,key,boot,nonce,1000,10001000,8081,
        policy(),"reviewed-recovery",healthy_runtime,&healthy));
    if(scenario==4)net.eof=true;
    if(scenario==5)clock.tick=10001000;
    if(scenario==6)runtime.interference();
    for(int i=0;i<100;++i){clock.tick+=20000;runtime.poll();}
    assert(bus.enables==0&&bus.writes==(scenario==0?1:0));
    if(scenario==0){
      assert(runtime.state()==SessionState::Captured&&runtime.size()==8);
      const int reads=bus.reads;char status[512],record[4608];
      assert(runtime.status_json(status,sizeof(status)));std::cout<<status<<"\n";
      for(size_t i=0;i<runtime.size();++i){assert(runtime.record_json(i,record,sizeof(record)));std::cout<<record<<"\n";}
      VerifiedHoldHandoff handoff;assert(!runtime.retire_to_pair(handoff));
      assert(runtime.size()==8&&bus.reads==reads); // Failed handoff must retain evidence.
    }else assert(runtime.state()==SessionState::Fault);
    assert(!runtime.exclusive_work());
  }
  return 0;
}

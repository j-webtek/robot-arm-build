#define HOLD_ADMISSION_NO_MAIN
#include "test_hold_plan_admission.cpp"
#undef HOLD_ADMISSION_NO_MAIN
int main(int argc,char** argv){
  assert(argc==3);std::ifstream file(argv[1],std::ios::binary);
  std::vector<uint8_t> token((std::istreambuf_iterator<char>(file)),{});
  uint8_t key[32],boot[16],nonce[32];memset(key,'k',32);memset(boot,0x11,16);memset(nonce,0x22,32);
  const bool valid=argv[2][0]=='1';Crypto crypto;
  // A recovery token cannot enter an ordinary hold admission path.
  HoldPlanAdmission ordinary(key,boot,nonce,1000,10001000);
  if(valid)assert(!ordinary.consume(token.data(),token.size(),1001,crypto,policy(),"reviewed-recovery"));
  for(int scenario=0;scenario<7;++scenario){
    bool healthy=true;GuardedBus bus;bus.healthy=&healthy;bus.automatic=false;
    bus.torque[3]=1;bus.goal[3]=2728;Clock clock;clock.tick=1001;RuntimeSink sink;
    if(scenario==1)sink.reserve_ok=false;
    if(scenario==2)sink.fail_at=0;
    if(scenario==3)bus.revoke_at=84;
    if(scenario==4)sink.fail_at=7;
    if(scenario==5)bus.lost_ack=true;
    if(scenario==6)clock.tick=10001000;
    HoldAuthenticatedRuntime<GuardedBus,Clock,RuntimeSink,Crypto,true> runtime(
      bus,clock,sink,crypto,key,boot,nonce,1000,10001000,policy(),
      "reviewed-recovery",healthy_runtime,&healthy);
    assert(runtime.start(token.data(),token.size())==(valid&&scenario!=1&&scenario!=2&&scenario!=6));
    assert(!runtime.start(token.data(),token.size()));
    for(int i=0;i<10;++i){clock.tick+=110000;runtime.poll();}
    if(!valid||scenario==1||scenario==2||scenario==3||scenario==6)assert(bus.writes==0);
    else assert(bus.writes==1);
    assert(bus.enables==0);
    VerifiedHoldHandoff handoff;assert(!runtime.take_handoff(handoff));
    if(valid&&scenario==0){
      assert(runtime.owner().phase()==HoldPhase::Captured&&sink.records.size()==8);
      for(const auto& record:sink.records)std::cout<<record<<"\n";
    }
    const int reads=bus.reads,writes=bus.writes;runtime.poll();
    assert(bus.reads==reads&&bus.writes==writes);
  }
}

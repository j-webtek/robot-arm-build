// Reuse the ordinary-hold scripted bus; no device or network access.
#define main ordinary_hold_regressions
#include "test_hold_initialization_owner.cpp"
#undef main

int main(){
  assert(ordinary_hold_regressions()==0);
  for(int residual=-6;residual<=6;++residual){
    Bus bus;Clock clock;bus.automatic=false;bus.torque[3]=1;
    bus.goal[3]=2723+residual;
    HoldInitializationOwner owner(policy(),SupportedRecoveryAdmission{});
    run(owner,bus,clock);
    const bool allowed=residual>=-5&&residual<=5;
    assert(owner.supported_recovery());
    assert(owner.phase()==(allowed?HoldPhase::Captured:HoldPhase::Fault));
    assert(bus.writes==(allowed?1:0)&&bus.enables==0);
    if(allowed)assert(bus.goal[3]==2723&&owner.scan_count()==5);
    int reads=bus.reads;run(owner,bus,clock);assert(bus.reads==reads);
  }
  // Every capture read can fail: never retry or issue an enable command.
  for(int failed=0;failed<140;++failed){
    Bus bus;Clock clock;bus.torque[3]=1;bus.goal[3]=2728;bus.bad=failed;
    HoldInitializationOwner owner(policy(),SupportedRecoveryAdmission{});
    run(owner,bus,clock);assert(owner.phase()==HoldPhase::Fault);
    assert(bus.writes<=1&&bus.enables==0);
    int reads=bus.reads,writes=bus.writes;run(owner,bus,clock);
    assert(bus.reads==reads&&bus.writes==writes);
  }
  for(int fault=0;fault<9;++fault){
    Bus bus;Clock clock;bus.automatic=false;bus.torque[3]=1;bus.goal[3]=2728;
    auto p=policy();
    if(fault==0)p.permit_explicit_enable=true;
    if(fault==1)p.drift=3;
    if(fault==2)p.speed=21;
    if(fault==3)bus.torque[3]=0;
    if(fault==4)bus.elbow_moving=1;
    if(fault==5)p.maximum[3]=2727; // old goal outside envelope
    HoldInitializationOwner owner(p,SupportedRecoveryAdmission{});
    step(owner,bus,clock);step(owner,bus,clock);
    if(fault==6)bus.goal[3]=2727; // changed baseline
    if(fault==7)bus.position[1]+=3; // neighbor drift
    if(fault==8)bus.position[3]-=1; // initial residual now exceeds five
    run(owner,bus,clock);
    assert(owner.phase()==HoldPhase::Fault&&bus.writes==0&&bus.enables==0);
  }
  for(int fault=0;fault<4;++fault){
    Bus bus;Clock clock;bus.automatic=false;bus.torque[3]=1;bus.goal[3]=2728;
    if(fault==0)bus.lost_ack=true;
    if(fault==1)bus.ignore_goal=true;
    HoldInitializationOwner owner(policy(),SupportedRecoveryAdmission{});
    step(owner,bus,clock);step(owner,bus,clock);step(owner,bus,clock);
    assert(bus.writes==1);
    if(fault==2)bus.torque[3]=0;
    if(fault==3)bus.position[3]+=3; // arrival is still two counts, not five
    run(owner,bus,clock);
    assert(owner.phase()==HoldPhase::Fault&&bus.writes==1&&bus.enables==0);
  }
  return 0;
}

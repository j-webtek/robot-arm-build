#include <new>
#include <cstdlib>
bool fail_hold_allocation=false;
unsigned hold_allocation_attempts=0;
void* operator new(size_t size,const std::nothrow_t&) noexcept {
  ++hold_allocation_attempts;
  if(fail_hold_allocation)return nullptr;
  try{return ::operator new(size);}catch(...){return nullptr;}
}
void operator delete(void* value,const std::nothrow_t&) noexcept {::operator delete(value);}
#define HOLD_ADMISSION_NO_MAIN
#include "test_hold_plan_admission.cpp"
#undef HOLD_ADMISSION_NO_MAIN
#include "allocated_hold_runtime.h"
int main(int argc,char** argv){
  assert(argc==2);std::ifstream file(argv[1],std::ios::binary);
  std::vector<uint8_t> token((std::istreambuf_iterator<char>(file)),{});
  uint8_t key[32],boot[16],nonce[32];memset(key,'k',32);memset(boot,0x11,16);memset(nonce,0x22,32);
  using Allocated=rocell_diag::AllocatedHoldRuntime<GuardedBus,Clock,Crypto>;
  for(int scenario=0;scenario<5;++scenario){
    GuardedBus bus;Clock clock;clock.tick=1001;Crypto crypto;bool healthy=true;bus.healthy=&healthy;
    auto p=policy();if(scenario==1)p.speed=0;if(scenario==2)healthy=false;
    if(scenario==3)clock.tick=10001000;
    fail_hold_allocation=scenario==4;const auto attempts=hold_allocation_attempts;
    Allocated runtime;assert(!runtime.start(token.data(),token.size()));runtime.poll();
    const bool initialized=runtime.initialize(bus,clock,crypto,key,boot,nonce,1000,10001000,p,
        "reviewed-hold",healthy_runtime,&healthy);
    assert(initialized==(scenario==0));
    assert(hold_allocation_attempts-attempts==unsigned(scenario==0||scenario==4));
    assert(bus.reads==0&&bus.writes==0);
    assert(!runtime.initialize(bus,clock,crypto,key,boot,nonce,1000,10001000,p,
        "reviewed-hold",healthy_runtime,&healthy));
    if(initialized){
      assert(runtime.start(token.data(),token.size()));
      for(int i=0;i<10;++i){clock.tick+=110000;runtime.poll();}
      assert(runtime.owner()->phase()==rocell_diag::HoldPhase::Captured&&runtime.size()==8);
      assert(bus.writes==1&&!runtime.storage_faulted()&&runtime.get(7));
    }else {assert(!runtime.start(token.data(),token.size()));runtime.poll();assert(bus.reads==0&&bus.writes==0);}
  }
}

#define HOLD_ADMISSION_NO_MAIN
#define Bus HoldFixtureBus
#define Clock HoldFixtureClock
#define policy hold_fixture_policy
#include "test_hold_plan_admission.cpp"
#undef policy
#undef Clock
#undef Bus
#define main run_leg_cases
#include "test_held_elbow_leg_owner.cpp"
#undef main
#include "held_stored_return_admission.h"
#include "held_pair_return_bridge.h"
#include "held_elbow_pair_owner.h"
#include <memory>
struct StoredDriver {
  Bus& bus;Clock& clock;HeldLegEvidencePublisher& publisher;EvidenceStore<34,4096>& store;
  void poll(HeldElbowLegOwner& owner){clock.tick+=110000;publisher.poll(owner,bus,clock,store);}
};
#ifndef HELD_STORED_NO_MAIN
int main(int argc,char** argv){
  assert(argc==2||argc==4);
  const char* boot_text="11111111111111111111111111111111";
  Bus bus;Clock clock;Crypto crypto;
  HoldStateSnapshot held;auto p=policy();
  assert(held.capture(bus,clock,p.pair_us,p.scan_us));
  auto pair=std::unique_ptr<HeldElbowPairOwner>(new HeldElbowPairOwner(p,6,2,healthy));
  assert(pair->start(held));
  auto store=std::unique_ptr<EvidenceStore<34,4096>>(new EvidenceStore<34,4096>());
  auto publisher=std::unique_ptr<HeldLegEvidencePublisher>(new HeldLegEvidencePublisher());
  assert(publisher->begin(*store,boot_text,"forward"));
  StoredDriver driver{bus,clock,*publisher,*store};
  for(int i=0;i<30;++i)pair->poll(driver);
  assert(pair->phase()==HeldPairPhase::AwaitingExport&&store->size()==7);
  if(argc==2){
    for(size_t i=0;i<store->size();++i)std::cout<<store->get(i)->kind<<"\t"<<store->get(i)->json<<"\n";
    return 0;
  }
  auto copied=std::unique_ptr<EvidenceStore<34,4096>>(new EvidenceStore<34,4096>());
  const int mutate=std::stoi(argv[3]);
  for(size_t i=0;i<store->size();++i){
    std::string raw=store->get(i)->json;if(int(i)==mutate)raw+=" ";
    assert(copied->publish(store->get(i)->kind,raw.c_str()));
  }
  std::ifstream file(argv[1],std::ios::binary);
  std::vector<uint8_t> token((std::istreambuf_iterator<char>(file)),{});
  uint8_t key[32],boot[16],nonce[32];memset(key,'k',32);memset(boot,0x11,16);memset(nonce,0x22,32);
  std::string session(64,'a'),plan(64,'b');
  HeldReturnAdmission gate(key,boot,nonce,1000,10001000);
  using Bridge=HeldPairReturnBridge<EvidenceStore<34,4096>,Crypto,Clock>;
  auto bridge=std::unique_ptr<Bridge>(new Bridge(gate,token.data(),token.size(),crypto,clock,
                                               *copied,boot_text,"forward",session.c_str(),plan.c_str()));
  const int reads=bus.reads,writes=bus.writes;
  bool ok=pair->admit_return(*bridge);
  assert(ok==(argv[2][0]=='1'));
  assert(!pair->admit_return(*bridge));
  assert(bus.reads==reads&&bus.writes==writes); // Authentication never touches bus.
  if(ok){
    assert(pair->phase()==HeldPairPhase::Return);
    // Forward evidence is released only after successful signature admission.
    bridge.reset();
    publisher.reset();store.reset();copied.reset();
    publisher.reset(new HeldLegEvidencePublisher());store.reset(new EvidenceStore<34,4096>());
    assert(publisher->begin(*store,boot_text,"return"));
    if(mutate==-2)bus.pos[1]+=3;
    if(mutate==-3)assert(!store->publish("record_kind_too_long","{}"));
    StoredDriver reverse{bus,clock,*publisher,*store};
    for(int i=0;i<30;++i)pair->poll(reverse);
    if(mutate==-2||mutate==-3){
      assert(pair->phase()==HeldPairPhase::Stopped&&bus.writes==1);
    }else{
      assert(pair->phase()==HeldPairPhase::Complete&&bus.writes==2&&bus.pos[3]==2902);
      assert(store->size()==7&&!store->faulted());
      assert(strstr(store->get(6)->json,"ARRIVED"));
    }
  }else{
    assert(pair->phase()==HeldPairPhase::Stopped);
    for(int i=0;i<30;++i)pair->poll(driver);
    assert(bus.reads==reads&&bus.writes==writes&&writes==1);
  }
  return 0;
}
#endif

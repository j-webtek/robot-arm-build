#define HELD_PAIR_NO_MAIN
#include "test_held_elbow_pair_owner.cpp"
#include "held_leg_evidence_publisher.h"
#include "evidence_store.h"
#include <memory>
struct PublishedDriver {
  Bus& bus;Clock& clock;
  std::unique_ptr<EvidenceStore<34,4096>> store;
  std::unique_ptr<HeldLegEvidencePublisher> publisher;
  PublishedDriver(Bus& b,Clock& c):bus(b),clock(c){begin("forward");}
  void begin(const char* command){
    // Test-only rollover after admission, deliberately reuse one store lifetime.
    publisher.reset();store.reset();
    store.reset(new EvidenceStore<34,4096>());
    publisher.reset(new HeldLegEvidencePublisher());
    assert(publisher->begin(*store,"test-boot",command));
  }
  void poll(HeldElbowLegOwner& leg){
    clock.tick+=110000;publisher->poll(leg,bus,clock,*store);
  }
};
int main(){
  assert(run_pair_cases()==0);
  for(int direction:{-1,1}){
    Bus bus;Clock clock;auto p=policy();HoldStateSnapshot held;
    assert(held.capture(bus,clock,p.pair_us,p.scan_us));
    auto pair=std::unique_ptr<HeldElbowPairOwner>(new HeldElbowPairOwner(p,6*direction,2,healthy));
    PublishedDriver driver(bus,clock);assert(pair->start(held));
    for(int i=0;i<30;++i)pair->poll(driver);
    assert(pair->phase()==HeldPairPhase::AwaitingExport);
    assert(!driver.store->faulted()&&driver.store->size()==7);
    assert(!strcmp(driver.store->get(6)->kind,"held_leg_end"));
    assert(strstr(driver.store->get(6)->json,"ARRIVED"));
    // Preserve output before releasing the forward store. This is not a host
    // durable-export proof; the production continuation adapter remains needed.
    std::string forward_terminal=driver.store->get(6)->json;
    const int reads=bus.reads;
    for(int i=0;i<30;++i)pair->poll(driver);
    assert(bus.reads==reads&&driver.store->size()==7);
    Admission admission;assert(pair->admit_return(admission));
    driver.begin("return");
    for(int i=0;i<30;++i)pair->poll(driver);
    assert(pair->phase()==HeldPairPhase::Complete&&bus.writes==2);
    assert(!driver.store->faulted()&&driver.store->size()==7);
    assert(strstr(driver.store->get(6)->json,"ARRIVED"));
    assert(strstr(forward_terminal.c_str(),"forward"));
    assert(strstr(driver.store->get(6)->json,"return"));
    assert(bus.pos[3]==2902);
  }
  return 0;
}

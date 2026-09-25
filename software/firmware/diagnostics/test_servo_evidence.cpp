#include "servo_evidence.h"
#include "servo_evidence_json.h"
#include "command_capture.h"
#include "callback_handoff.h"
#include <assert.h>
#include <stdio.h>
#include <thread>
using namespace rocell_diag;

struct Clock { uint64_t t = 1000; uint64_t now_us() { return ++t; } };
struct Bus {
  int calls = 0; bool fail = false; int error = 0;
  BusReadResult read(uint8_t id, uint8_t address, uint8_t width, uint8_t* bytes) {
    assert(id == 14);  // Elbow joint 3 is bus servo 14 in the pinned reference.
    assert((address == 42 && width == 2) || (address == 56 && width == 15));
    ++calls; bytes[0] = 0x34; bytes[1] = 0x08; // 2100, little endian.
    return {fail ? width - 1 : width, error};
  }
};

int main() {
  assert(record_dispatch(14,1,0,AckPolicy::Enabled).status == DispatchStatus::Succeeded);
  assert(record_dispatch(14,1,0,AckPolicy::Disabled).status == DispatchStatus::Unknown);
  assert(record_dispatch(14,1,0,AckPolicy::Unknown).status == DispatchStatus::Unknown);
  assert(record_dispatch(254,1,0,AckPolicy::Enabled).status == DispatchStatus::Unknown);
  assert(record_dispatch(14,0,0,AckPolicy::Enabled).status == DispatchStatus::Failed);
  assert(record_dispatch(14,1,32,AckPolicy::Enabled).status == DispatchStatus::Failed);
  assert(record_dispatch(14,1,-1,AckPolicy::Enabled).status == DispatchStatus::Unknown);
  Clock clock; Bus bus; PairRecorder recorder; PairEvidence pair;
  assert(recorder.acquire(14,bus,clock,pair));
  assert(pair.target.sequence == 0 && pair.feedback.sequence == 1);
  assert(pair.feedback.started_us > pair.target.finished_us);
  assert(pair.feedback.bytes[0] == 0x34 && pair.feedback.bytes[1] == 0x08);
  // Emit actual captured records for the host contract test, not a parallel fixture.
  char json[2048];
  assert(pair_json(pair,"simulation-boot","simulation-command","little",json,sizeof(json)));
  puts(json);
  char tiny[4]={'x','x','x','x'};
  assert(!pair_json(pair,"boot","command","little",tiny,sizeof(tiny)) && tiny[0]==0);
  assert(!pair_json(pair,"bad\"id","command","little",json,sizeof(json)) && json[0]==0);
  assert(!pair_json(pair,"boot","command","guess",json,sizeof(json)));
  char long_id[130]; for (char& c : long_id) c='a'; long_id[129]=0;
  assert(!pair_json(pair,long_id,"command","little",json,sizeof(json)));
  bus.fail = true;
  assert(!recorder.acquire(14,bus,clock,pair));
  assert(pair.feedback.status == ReadStatus::Failed);
  for (uint8_t byte : pair.feedback.bytes) assert(byte == 0);
  assert(pair_json(pair,"simulation-boot","simulation-command","little",json,sizeof(json)));
  puts(json);
  const int stopped_calls = bus.calls;
  assert(!recorder.acquire(14,bus,clock,pair) && bus.calls == stopped_calls);
  assert(pair.target.status == ReadStatus::Failed && pair.target.width == 0);
  Bus error_bus; error_bus.error=4; PairRecorder second;
  assert(!second.acquire(14,error_bus,clock,pair));
  assert(pair.target.device_error == 4 && pair.target.status == ReadStatus::Failed);
  Bus invalid_bus; PairRecorder invalid;
  assert(!invalid.acquire(254,invalid_bus,clock,pair) && invalid_bus.calls == 0);
  Bus rewind_bus; PairRecorder rewind; Clock rewind_clock;
  assert(rewind.acquire(14,rewind_bus,rewind_clock,pair));
  rewind_clock.t=1000;
  assert(!rewind.acquire(14,rewind_bus,rewind_clock,pair));
  assert(rewind.faulted());
  CommandCapture capture; Clock capture_clock; Bus capture_bus;
  char identity[]="simulation-command";
  assert(capture.begin("simulation-boot",identity,14,2100,20,1,1000,
      1,0,AckPolicy::Enabled,1,100));
  identity[0]='x'; // Capture owns identity; subsequent caller mutation is harmless.
  assert(capture.acquire(capture_bus,capture_clock,pair));
  pair.target.bytes[0]=0; // Caller mutation cannot alter the retained acquisition.
  assert(capture.encode_pair("little",json,sizeof(json)));puts(json);
  assert(capture.encode_dispatch(json,sizeof(json)));puts(json);
  assert(capture.encode_write_evidence(json,sizeof(json)));puts(json);
  assert(!capture.encode_write_evidence(tiny,sizeof(tiny)) && tiny[0]==0);
  const int finite_calls=capture_bus.calls;
  assert(!capture.acquire(capture_bus,capture_clock,pair));
  assert(capture_bus.calls==finite_calls && capture.stopped());
  assert(!capture.begin("boot","another",14,2100,20,1,1000,1,0,AckPolicy::Enabled,1,100));
  CommandCapture uncertain; Bus uncertain_bus;
  assert(uncertain.begin("boot","uncertain",14,2100,20,1,1000,1,0,AckPolicy::Disabled,1,100));
  assert(uncertain.stopped());
  assert(!uncertain.acquire(uncertain_bus,capture_clock,pair) && uncertain_bus.calls==0);
  assert(uncertain.write_evidence().library_return==1);
  CommandCapture stale; Bus stale_bus; Clock stale_clock;
  assert(stale.begin("boot","stale",14,2100,20,1,2000,1,0,AckPolicy::Enabled,1,100));
  assert(!stale.acquire(stale_bus,stale_clock,pair) && stale.stopped());
  CallbackHandoff<4,2> handoff;CallbackHandoff<4,2>::Packet queued;
  uint8_t sender[6]={1,2,3,4,5,6}, message[4]={7,8,9,10};
  assert(handoff.push(sender,message,4));
  sender[0]=99;message[0]=88;
  assert(handoff.pop(queued) && queued.sender[0]==1 && queued.bytes[0]==7);
  assert(!handoff.pop(queued) && !handoff.faulted());
  assert(handoff.push(sender,message,4));message[0]=77;
  assert(handoff.push(sender,message,4));
  assert(handoff.pop(queued) && queued.bytes[0]==88);
  assert(handoff.pop(queued) && queued.bytes[0]==77);
  assert(handoff.push(sender,message,4));assert(handoff.push(sender,message,4));
  assert(!handoff.push(sender,message,4) && handoff.faulted());
  assert(!handoff.pop(queued) && queued.bytes[0]==0);
  CallbackHandoff<4> truncated;
  assert(!truncated.push(sender,message,3) && truncated.faulted());
  assert(!truncated.push(sender,message,4));
  for (int trial=0;trial<100;++trial) {
    CallbackHandoff<4,2> concurrent;std::atomic<bool> start(false);
    const uint8_t first[4]={1,1,1,1},second_msg[4]={2,2,2,2};
    std::thread a([&]{while (!start.load()) {} concurrent.push(sender,first,4);});
    std::thread b([&]{while (!start.load()) {} concurrent.push(sender,second_msg,4);});
    start.store(true);a.join();b.join();
    if (concurrent.faulted()) assert(!concurrent.pop(queued));
    else {
      assert(concurrent.pop(queued));const uint8_t first_value=queued.bytes[0];
      for (uint8_t value : queued.bytes) assert(value==first_value);
      assert(concurrent.pop(queued));assert(queued.bytes[0]!=first_value);
      for (uint8_t value : queued.bytes) assert(value==queued.bytes[0]);
      assert(!concurrent.pop(queued));
    }
  }
  return 0;
}

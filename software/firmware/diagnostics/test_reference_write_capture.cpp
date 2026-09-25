#include "reference_write_capture.h"
#include <cassert>
#include <cstdio>
using namespace rocell_diag;
struct Library {
  int Level=1,Error=32,result=1,calls=0;
  int WritePosEx(uint8_t id,int16_t target,uint16_t speed,uint8_t acceleration) {
    ++calls;assert(id==14 && target==2100 && speed==20 && acceleration==1);
    return result;
  }
};
struct Clock {
  uint64_t t=1000;bool rewind=false;
  uint64_t now_us() { return rewind?--t:++t; }
};
int main() {
  for (int scenario=0;scenario<6;++scenario) {
    Library bus;Clock clock;ReferenceWriteCapture hook;
    bus.Error=scenario==1?32:0;
    if (scenario==2) bus.result=0;
    if (scenario==3) bus.Level=0;
    if (scenario==4) clock.rewind=true;
    const bool ok=hook.dispatch(bus,clock,"boot","command",14,
        scenario==5?4096:2100,20,1,2,100);
    assert(ok==(scenario==0));
    assert(hook.capture().stopped()==(scenario!=0));
    assert(bus.calls==(scenario==5?0:1));
    assert(!hook.dispatch(bus,clock,"boot","other",14,2100,20,1,2,100));
    assert(bus.calls==(scenario==5?0:1));
    if (scenario==2 || scenario==3) assert(hook.capture().write_evidence().device_error==-1);
    char output[1024];
    if (scenario==0) {
      assert(hook.capture().encode_dispatch(output,sizeof(output)));puts(output);
      assert(hook.capture().encode_write_evidence(output,sizeof(output)));puts(output);
    }
    assert(hook.encode_outcome(output,sizeof(output)));puts(output);
  }
}

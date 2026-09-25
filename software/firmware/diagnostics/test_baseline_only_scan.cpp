#include <cassert>
#include <cstddef>
#include <cstring>
#include "baseline_only_scan.h"
#include "baseline_only_json.h"
struct Clock {uint64_t tick=1000,step=1;uint64_t now_us(){return tick+=step;}};
// Deliberately has NO servo-write methods: accidental write coupling cannot
// compile. Read transactions still send read requests on the servo bus.
struct ReadOnlyBus {
  int End=0,Error=0,reads=0,bad_read=-1,mode=0;
  int Read(uint8_t id,uint8_t address,uint8_t* bytes,uint8_t width) {
    assert(id==11+reads/2);
    assert(address==(reads%2?56:42));
    assert(width==(reads%2?15:2));
    const int current=reads++;
    if(current==bad_read){
      if(mode==0)return 0;
      if(mode==1)return width-1;
      Error=1;
    }else Error=0;
    // An unsettled/unknown pose is evidence, not grounds to move to a target.
    bytes[0]=0x34;bytes[1]=0x08;
    if(width==15)bytes[10]=1;
    return width;
  }
};
int main(){
  {ReadOnlyBus bus;Clock clock;rocell_diag::BaselineOnlyScan scan;
   assert(scan.run(bus,clock,100,1000)&&scan.complete());
   assert(scan.count()==7&&bus.reads==14&&!scan.pair(7));
   assert(scan.pair(6)->feedback.bytes[10]==1);
   char json[2048];assert(rocell_diag::baseline_only_json(scan,"boot","scan",json,sizeof(json)));puts(json);
   char small[8];assert(!rocell_diag::baseline_only_json(scan,"boot","scan",small,sizeof(small)));
   assert(!scan.run(bus,clock,100,1000)&&bus.reads==14);}
  for(int read=0;read<14;++read)for(int mode=0;mode<3;++mode){
    ReadOnlyBus bus;Clock clock;bus.bad_read=read;bus.mode=mode;
    rocell_diag::BaselineOnlyScan scan;
    assert(!scan.run(bus,clock,100,1000)&&!scan.complete());
    assert(scan.count()==static_cast<size_t>(read/2+1));
    assert(bus.reads==(read/2+1)*2); // Finish failed pair, never later joints.
    const auto* pair=scan.pair(read/2);
    const auto& failed=read%2?pair->feedback:pair->target;
    assert(failed.status==rocell_diag::ReadStatus::Failed&&failed.bytes[0]==0);
    const int before=bus.reads;
    if(read==5 && mode==0){char json[2048];assert(rocell_diag::baseline_only_json(scan,"boot","scan",json,sizeof(json)));puts(json);}
    assert(!scan.run(bus,clock,100,1000)&&bus.reads==before);
  }
  {ReadOnlyBus bus;Clock clock;bus.End=1;rocell_diag::BaselineOnlyScan scan;
   assert(!scan.run(bus,clock,100,1000)&&bus.reads==0);}
  {ReadOnlyBus bus;Clock clock;clock.step=100;rocell_diag::BaselineOnlyScan scan;
   assert(!scan.run(bus,clock,100,1000)&&bus.reads==2);
   assert(!strcmp(scan.reason(),"BASELINE_TIMING_INVALID"));}
  {ReadOnlyBus bus;Clock clock;clock.step=0;rocell_diag::BaselineOnlyScan scan;
   assert(!scan.run(bus,clock,100,1000)&&bus.reads==2);}
  {ReadOnlyBus bus;Clock clock;rocell_diag::BaselineOnlyScan scan;
   assert(!scan.run(bus,clock,0,1000)&&bus.reads==0);}
}

#include "fresh_elbow_baseline.h"
#include <cassert>
using namespace rocell_diag;
struct Clock {
  uint64_t t=1000;int calls=0;bool stale=false;
  uint64_t now_us(){++calls;t+=(stale && calls==5)?1000:1;return t;}
};
struct Library {
  int End=0,Error=0,reads=0;bool bad=false,moving=false,off=false;
  int Read(uint8_t id,uint8_t address,uint8_t* data,uint8_t width){
    assert(id==14);++reads;
    unsigned count=(off && address==42)?2200:2100;
    data[0]=count&255;data[1]=count>>8;
    if(width==15)data[10]=moving?1:0;
    return bad?0:width;
  }
};
int main(){
  for(int scenario=0;scenario<7;++scenario){
    Library library;Clock clock;FreshElbowBaseline gate;
    if(scenario==1)library.bad=true;
    if(scenario==2)library.moving=true;
    if(scenario==3)library.off=true;
    if(scenario==4)clock.stale=true;
    if(scenario==6)library.End=1;
    const bool accepted=gate.check(library,clock,scenario==5?2150:2110,16,2,100,100);
    assert(accepted==(scenario==0));
    assert(gate.accepted()==accepted);
    const int reads=library.reads;
    assert(!gate.check(library,clock,2110,16,2,100,100) && library.reads==reads);
    assert(reads==(scenario==6?0:2));
    char record[2048];assert(gate.encode("boot","command",record,sizeof(record))==(scenario!=6));
  }
}

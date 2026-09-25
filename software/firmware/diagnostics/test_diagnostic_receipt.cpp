#include "diagnostic_receipt.h"
#include <cassert>
#include <cstdio>
using namespace rocell_diag;
int main(){
  const char* good=" {\"T\":101, \"joint\":3,\"rad\":1.7,\"spd\":20,\"acc\":1} \n";
  DiagnosticReceipt receipt;char output[2048];
  assert(receipt.accept("boot","command",good,strlen(good),1000));
  // Pinned ArduinoJson stores this value at float precision; do not claim exact
  // decimal equality. Original payload is independently preserved byte for byte.
  assert(fabs(receipt.received_radians()-1.7)<1e-7 && receipt.speed()==20 && receipt.acceleration()==1);
  assert(!receipt.accept("boot","again",good,strlen(good),1001));
  assert(receipt.encode(output,sizeof(output)));puts(output);
  for(const char* bad:{
      "{\"T\":101,\"joint\":3,\"rad\":1.7,\"spd\":20,\"acc\":1,\"rad\":2}",
      "{\"T\":101,\"joint\":3,\"rad\":1.7,\"spd\":20,\"acc\":1}{}",
      "{\"T\":101,\"joint\":3,\"rad\":{},\"spd\":20,\"acc\":1}",
      "{\"T\":101,\"joint\":4,\"rad\":1.7,\"spd\":20,\"acc\":1}",
      "{\"T\":101,\"joint\":3,\"rad\":1.7,\"spd\":-1,\"acc\":1}",
      "{\"T\":101,\"joint\":3,\"rad\":1.7,\"spd\":20,\"acc\":256}"}){
    DiagnosticReceipt rejected;
    assert(!rejected.accept("boot","command",bad,strlen(bad),1000));
    assert(!rejected.accept("boot","command",good,strlen(good),1000));
    assert(!rejected.encode(output,sizeof(output)));
  }
}

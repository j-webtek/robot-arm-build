#include "reviewed_hover_recovery_board_adapter.h"
#include <cassert>
#include <cstdint>
using namespace rocell_diag;
struct Services {
  bool good=true,owner=false;
  bool healthy(){return good;}
  bool memory_fits(size_t,size_t){return true;}
  bool reserve(){if(owner)return false;owner=true;return true;}
  bool owned(){return owner;}
  bool air_typing_sample(ShoulderPreloadPose&){return true;}
  bool air_typing_evidence(const char*,const ShoulderPreloadPose&){return true;}
};
struct Bus {
  int End=0,Error=0;
  unsigned writes=0;
  void SyncWritePosEx(uint8_t*,uint8_t count,int16_t*,uint16_t*,uint8_t*){
    assert(count==7);++writes;
  }
};
int main(){
  Services services;Bus bus;
  ReviewedHoverRecoveryBoardAdapter<Services,Bus> adapter(services,bus);
  uint8_t release[32]{};
  assert(adapter.reviewed_hover_release_digest(release));
  assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[0],20,1));
  assert(adapter.reserve());
  for(unsigned row=0;row<3;++row)
    assert(adapter.reviewed_hover_write(ReviewedHoverManifest::goals[row],20,1));
  for(unsigned row=3;row<6;++row)
    assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[row],20,1));
  assert(bus.writes==3);
  assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[0],19,1));
  assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[0],20,2));
  bus.End=1;assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[0],20,1));
  bus.End=0;services.good=false;
  assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[0],20,1));
  services.good=true;bus.Error=1;
  assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[0],20,1));
  assert(bus.writes==4); // Attempted delivery is uncertain, never retried here.
  return 0;
}

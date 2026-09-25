#include "reviewed_hover_board_adapter.h"
#include <cassert>
#include <cstdint>

using namespace rocell_diag;
struct Services {
  bool good=true,has_owner=false,mem=true;
  unsigned reserves=0,samples=0,evidence=0;
  bool healthy(){return good;}
  bool memory_fits(size_t,size_t){return mem;}
  bool reserve(){++reserves;if(has_owner||!good)return false;has_owner=true;return true;}
  bool owned(){return has_owner;}
  bool air_typing_sample(ShoulderPreloadPose&){++samples;return true;}
  bool air_typing_evidence(const char*,const ShoulderPreloadPose&){++evidence;return true;}
};
struct Bus {
  int End=0,Error=0;
  unsigned writes=0;
  uint8_t ids[7]{},acc[7]{};
  int16_t targets[7]{};
  uint16_t speeds[7]{};
  void SyncWritePosEx(uint8_t* i,uint8_t count,int16_t* t,uint16_t* s,uint8_t* a){
    assert(count==7);++writes;
    for(unsigned j=0;j<7;++j){ids[j]=i[j];targets[j]=t[j];speeds[j]=s[j];acc[j]=a[j];}
  }
};
int main(){
  Services services;Bus bus;
  ReviewedHoverBoardAdapter<Services,Bus> adapter(services,bus);
  ShoulderPreloadPose pose{};
  assert(services.reserves==0&&services.samples==0&&bus.writes==0);
  uint8_t release[32];
  assert(adapter.reviewed_hover_release_digest(release));
  for(unsigned i=0;i<32;++i)
    assert(release[i]==reviewed_hover_release_sha256[i]);
  uint8_t recipe[32]{};
  assert(adapter.reviewed_hover_recipe_digest(recipe));
  static constexpr uint8_t pinned[32]={
    0x66,0x63,0xde,0xd0,0xb5,0x9a,0xe4,0xd5,
    0xe0,0xa8,0x9a,0x04,0x8c,0xf2,0x3f,0x1e,
    0x6f,0xe6,0x20,0xe7,0x91,0xbd,0xe4,0x97,
    0xc2,0x77,0x99,0x03,0x0c,0xdc,0x8f,0x16};
  for(unsigned i=0;i<32;++i)assert(recipe[i]==pinned[i]);
  assert(!adapter.reviewed_hover_sample(pose));
  assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[1],20,1));
  assert(adapter.reserve()&&!adapter.reserve()&&services.reserves==2);
  assert(adapter.memory_fits(100,200));
  services.mem=false;assert(!adapter.memory_fits(100,200));services.mem=true;
  assert(adapter.reviewed_hover_sample(pose)&&services.samples==1);
  assert(!adapter.reviewed_hover_evidence(nullptr,pose));
  assert(adapter.reviewed_hover_evidence("PREWRITE",pose)&&services.evidence==1);
  uint16_t altered[7];
  for(unsigned i=0;i<7;++i)altered[i]=ReviewedHoverManifest::goals[1][i];
  ++altered[4];
  assert(!adapter.reviewed_hover_write(altered,20,1));
  assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[1],21,1));
  assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[1],20,2));
  bus.End=1;assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[1],20,1));
  bus.End=0;services.good=false;
  assert(!adapter.reviewed_hover_sample(pose));
  assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[1],20,1));
  services.good=true;services.has_owner=false;
  assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[1],20,1));
  services.has_owner=true;
  assert(bus.writes==0);
  for(unsigned row=0;row<6;++row){
    assert(adapter.reviewed_hover_write(ReviewedHoverManifest::goals[row],20,1));
    assert(bus.writes==row+1);
    for(unsigned i=0;i<7;++i){
      assert(bus.ids[i]==11+i&&bus.targets[i]==ReviewedHoverManifest::goals[row][i]);
      assert(bus.speeds[i]==20&&bus.acc[i]==1);
    }
  }
  bus.Error=1;
  assert(!adapter.reviewed_hover_write(ReviewedHoverManifest::goals[1],20,1));
  assert(bus.writes==7); // Delivery uncertain; never retried by adapter.
  return 0;
}

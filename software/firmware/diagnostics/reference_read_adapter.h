// Only for the pinned SCS implementation WITH the reviewed response-ID/length
// guard. Not proof of installed compatibility. Existing controller owns the bus.
#pragma once
#include "servo_evidence.h"

namespace rocell_diag {
template <class IdentityCheckedSCS>
class ReferenceReadAdapter {
 public:
  explicit ReferenceReadAdapter(IdentityCheckedSCS& library) : library_(library) {}
  BusReadResult read(uint8_t id,uint8_t address,uint8_t width,uint8_t* destination) {
    if (!destination || id<1 || id>253 ||
        !((address==42 && width==2) || (address==56 && width==15))) return {0,-1};
    for (uint8_t i=0;i<width;++i) destination[i]=0;
    const int count=library_.Read(id,address,destination,width);
    // Error can be left over after early failure in SCS::Read. Only a complete
    // identity/checksum-validated response makes it transaction-specific.
    const int error=count==width ? library_.Error : -1;
    if (count!=width || error!=0)
      for (uint8_t i=0;i<width;++i) destination[i]=0;
    return {count,error};
  }
 private:
  IdentityCheckedSCS& library_;
};
} // namespace rocell_diag

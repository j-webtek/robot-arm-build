// The reviewed r7 filesystem remains unchanged. Only an explicit recovery route
// can derive this narrower enabled-only policy; unexpected settings are rejected.
#pragma once
#include "hold_initialization_owner.h"
namespace rocell_diag {
inline bool reviewed_recovery_source(const HoldInitializationPolicy& p){
  const uint16_t windows[7][2]={{1983,2111},{2326,2454},{1663,1791},{2893,2909},
                               {1977,2105},{1978,2106},{1987,2115}};
  for(size_t i=0;i<7;++i)if(p.minimum[i]!=windows[i][0]||p.maximum[i]!=windows[i][1])return false;
  return p.drift==2&&p.speed==20&&p.acceleration==1&&p.permit_explicit_enable&&
      p.age_us==250000&&p.baseline_gap_us==100000&&p.deadline_us==2000000&&
      p.maximum_gap_us==500000&&p.pair_us==10000&&p.scan_us==100000&&p.settle_us==100000;
}

// Separately reviewed observed-pose registration. Never treat an arbitrary
// valid JSON policy as recovery authorization. Legacy behavior stays unchanged.
inline bool reviewed_observed_recovery_source(const HoldInitializationPolicy& p){
  const uint16_t windows[7][2]={{2045,2049},{2485,2489},{1627,1631},{2893,2909},
                               {2033,2037},{2039,2043},{2052,2056}};
  for(size_t i=0;i<7;++i)if(p.minimum[i]!=windows[i][0]||p.maximum[i]!=windows[i][1])return false;
  return p.drift==2&&p.speed==20&&p.acceleration==1&&!p.permit_explicit_enable&&
      p.age_us==250000&&p.baseline_gap_us==100000&&p.deadline_us==2000000&&
      p.maximum_gap_us==500000&&p.pair_us==10000&&p.scan_us==100000&&p.settle_us==100000;
}
}

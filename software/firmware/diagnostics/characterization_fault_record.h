// Read-only serialization of retained faults. No allocation, bus or recovery API.
#pragma once
#include "shoulder_characterization_owner.h"
namespace rocell_diag {
inline size_t encode_characterization_fault(const CharacterizationFault& fault,
                                            uint8_t* output,size_t capacity){
  if(!fault.present||!output||!fault.reason)return 0;
  size_t reason_size=0;
  while(reason_size<64&&fault.reason[reason_size])++reason_size;
  if(!reason_size||reason_size==64)return 0;
  const size_t required=11+1+reason_size+1+1+1+8+1+(fault.has_last_valid_pose?156:0);
  if(capacity<required||fault.leg>12||fault.writes>12)return 0;
  size_t offset=0;
  auto put=[&](uint64_t value,unsigned width){
    for(int i=int(width)-1;i>=0;--i)output[offset++]=uint8_t(value>>(8*i));
  };
  const char domain[]="RCCFAULT01";
  for(char c:domain)put(uint8_t(c),1);
  put(reason_size,1);for(size_t i=0;i<reason_size;++i)put(uint8_t(fault.reason[i]),1);
  put(static_cast<unsigned>(fault.phase),1);put(fault.leg,1);put(fault.writes,1);
  put(fault.last_owner_time_us,8);put(fault.has_last_valid_pose?1:0,1);
  if(fault.has_last_valid_pose){
    const auto& p=fault.last_valid_pose;
    put(p.started_us,8);put(p.finished_us,8);
    for(int i=0;i<7;++i){put(p.position[i],2);put(p.goal[i],2);put(p.torque[i],1);
      for(auto byte:p.feedback[i])put(byte,1);}
  }
  return offset;
}
}

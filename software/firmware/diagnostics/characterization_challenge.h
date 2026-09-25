// Public challenge contains no key. Source authenticity is a transport concern.
#pragma once
#include "characterization_prepare.h"
namespace rocell_diag {
inline size_t encode_characterization_challenge(const PreparedCharacterization& p,
    const uint8_t (&boot)[16],uint8_t* output,size_t capacity){
  if(!output||!p.manifest.legs||p.manifest.legs>12)return 0;
  const size_t required=11+16+32+32+32+16+1+8+28+4*p.manifest.legs;
  if(capacity<required)return 0;
  size_t count=0;
  auto put=[&](uint64_t value,unsigned width){for(int i=int(width)-1;i>=0;--i)output[count++]=uint8_t(value>>(8*i));};
  const char domain[]="RCCCHAL001";for(char c:domain)put(uint8_t(c),1);
  for(auto b:boot)put(b,1);for(auto b:p.nonce)put(b,1);
  for(auto b:p.campaign)put(b,1);for(auto b:p.reference)put(b,1);
  put(p.issued_us,8);put(p.expires_us,8);put(p.manifest.legs,1);put(p.manifest.maximum_us,8);
  for(auto& pair:p.manifest.bounds)for(auto value:pair)put(value,2);
  for(unsigned i=0;i<p.manifest.legs;++i)for(auto value:p.manifest.goals[i])put(value,2);
  return count;
}
}

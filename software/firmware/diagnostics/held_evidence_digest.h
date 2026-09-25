// Byte-exact bounded evidence identity. This does not prove arrival, origin,
// authentication or host durability. Keep the scratch object off task stacks.
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
namespace rocell_diag {
class HeldEvidenceDigest {
 public:
  template<class Store,class Crypto> bool compute(const Store& store,Crypto& crypto){
    valid_=false;output_[0]=0;
    if(store.faulted()||store.size()<1||store.size()>34)return false;
    static const char domain[]="rocell.held-evidence-chain.v1";
    uint8_t digest[32];
    if(!crypto.sha256(reinterpret_cast<const uint8_t*>(domain),sizeof(domain),digest))return false;
    for(size_t i=0;i<store.size();++i){
      const auto* record=store.get(i);if(!record)return false;
      size_t k=0,n=0;
      while(k<16&&record->kind[k])++k;
      while(n<4096&&record->json[n])++n;
      if(k==0||k>=16||n==0||n>=4096)return false;
      if(strcmp(record->kind,"held_leg_scan")&&strcmp(record->kind,"held_leg_action")&&
         strcmp(record->kind,"held_leg_end"))return false;
      size_t at=0;memcpy(scratch_,digest,32);at=32;
      scratch_[at++]=uint8_t(i>>8);scratch_[at++]=uint8_t(i);
      scratch_[at++]=uint8_t(k);memcpy(scratch_+at,record->kind,k);at+=k;
      scratch_[at++]=uint8_t(n>>8);scratch_[at++]=uint8_t(n);
      memcpy(scratch_+at,record->json,n);at+=n;
      if(!crypto.sha256(scratch_,at,digest))return false;
    }
    const char* hex="0123456789abcdef";
    for(size_t i=0;i<32;++i){output_[2*i]=hex[digest[i]>>4];output_[2*i+1]=hex[digest[i]&15];}
    output_[64]=0;valid_=true;return true;
  }
  const char* value()const{return valid_?output_:nullptr;}
 private:
  uint8_t scratch_[4160]={};char output_[65]={};bool valid_=false;
};
}

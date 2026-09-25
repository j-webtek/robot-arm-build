// Exact host-export receipt authentication. Uses supplied standard SHA/HMAC.
#pragma once
#include <cstdint>
#include <cstring>
namespace rocell_diag {
struct ShoulderReceiptView {const uint8_t* bytes;size_t size;};
template<class Crypto> class ShoulderReceiptVerifier {
 public:
  ShoulderReceiptVerifier(Crypto& crypto,const uint8_t (&key)[32],const uint8_t (&boot)[16],const char* command)
      :crypto_(crypto){
    memcpy(key_,key,32);memcpy(boot_,boot,16);
    size_t n=0;if(command)while(n<=128&&command[n])++n;
    valid_=n>0&&n<=128&&crypto_.sha256(reinterpret_cast<const uint8_t*>(command),n,command_hash_);
  }
  ~ShoulderReceiptVerifier(){volatile uint8_t* p=key_;for(size_t i=0;i<32;++i)p[i]=0;}
  ShoulderReceiptVerifier(const ShoulderReceiptVerifier&)=delete;
  ShoulderReceiptVerifier& operator=(const ShoulderReceiptVerifier&)=delete;
  bool verify(const ShoulderReceiptView& receipt,unsigned sequence,const uint8_t* digest){
    if(!valid_||!receipt.bytes||receipt.size!=124||sequence>=64||!digest)return false;
    const uint8_t* p=receipt.bytes;uint8_t expected[32]={};
    if(memcmp(p,"RCSHEX01",8)||memcmp(p+8,boot_,16)||memcmp(p+24,command_hash_,32))return false;
    const uint32_t seq=uint32_t(p[56])|(uint32_t(p[57])<<8)|(uint32_t(p[58])<<16)|(uint32_t(p[59])<<24);
    if(seq!=sequence||memcmp(p+60,digest,32)||!crypto_.hmac_sha256(key_,p,92,expected))return false;
    uint8_t difference=0;for(size_t i=0;i<32;++i)difference|=expected[i]^p[92+i];
    return difference==0;
  }
 private:
  Crypto& crypto_;bool valid_=false;uint8_t key_[32]={},boot_[16]={},command_hash_[32]={};
};
}

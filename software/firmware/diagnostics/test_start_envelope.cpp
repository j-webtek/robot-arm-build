// Windows host uses its actual HMAC provider, not a fake verification callback.
#include <windows.h>
#include <bcrypt.h>
#include <fstream>
#include <vector>
#include <iterator>
#include <cassert>
#include "start_envelope.h"
struct WindowsCrypto {
  bool hmac_sha256(const uint8_t (&key)[32],const uint8_t* data,size_t length,uint8_t (&out)[32]) {
    BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,BCRYPT_ALG_HANDLE_HMAC_FLAG)<0)return false;
    NTSTATUS result=BCryptCreateHash(algorithm,&hash,nullptr,0,const_cast<PUCHAR>(key),32,0);
    if(result>=0)result=BCryptHashData(hash,const_cast<PUCHAR>(data),static_cast<ULONG>(length),0);
    if(result>=0)result=BCryptFinishHash(hash,out,32,0);
    if(hash)BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(algorithm,0);return result>=0;
  }
};
struct FailedCrypto {
  bool hmac_sha256(const uint8_t (&)[32],const uint8_t*,size_t,uint8_t (&)[32]){return false;}
};
int main(int argc,char** argv){
  assert(argc==4);
  std::ifstream stream(argv[1],std::ios::binary);
  std::vector<uint8_t> token((std::istreambuf_iterator<char>(stream)),{});
  uint8_t key[32],boot[16],nonce[32];
  for(int i=0;i<32;++i){key[i]=i;nonce[i]=0x22;}
  for(auto& byte:boot)byte=0x11;
  rocell_diag::StartEnvelopeGate gate(key,boot,nonce,1000,11000);
  WindowsCrypto crypto;rocell_diag::AuthenticatedPlanView view;
  bool ok=gate.consume(token.data(),token.size(),strtoull(argv[2],nullptr,10),crypto,view);
  assert(ok==(strcmp(argv[3],"yes")==0));
  if(ok){assert(view.length>0);fwrite(view.bytes,1,view.length,stdout);}
  else assert(!view.bytes && !view.length);
  assert(!gate.consume(token.data(),token.size(),1001,crypto,view));
  assert(!view.bytes && !view.length);
  uint8_t zero[32]={};
  rocell_diag::StartEnvelopeGate zero_key(zero,boot,nonce,1000,11000);
  assert(!zero_key.consume(token.data(),token.size(),1001,crypto,view));
  rocell_diag::StartEnvelopeGate bad_lease(key,boot,nonce,1000,30001001);
  assert(!bad_lease.consume(token.data(),token.size(),1001,crypto,view));
  rocell_diag::StartEnvelopeGate broken_crypto(key,boot,nonce,1000,11000);
  FailedCrypto failure;
  assert(!broken_crypto.consume(token.data(),token.size(),1001,failure,view));
  assert(!broken_crypto.consume(token.data(),token.size(),1001,crypto,view));
}

#include <windows.h>
#include <bcrypt.h>
#include <fstream>
#include <vector>
#include <iterator>
#include <cassert>
#include "shoulder_export_receipt.h"
#include "characterization_export_barrier.h"
struct Crypto {
 bool hash(const uint8_t* key,const uint8_t* data,size_t length,uint8_t* out){
   BCRYPT_ALG_HANDLE a=nullptr;BCRYPT_HASH_HANDLE h=nullptr;
   if(BCryptOpenAlgorithmProvider(&a,BCRYPT_SHA256_ALGORITHM,nullptr,key?BCRYPT_ALG_HANDLE_HMAC_FLAG:0)<0)return false;
   auto result=BCryptCreateHash(a,&h,nullptr,0,const_cast<PUCHAR>(key),key?32:0,0);
   if(result>=0)result=BCryptHashData(h,const_cast<PUCHAR>(data),ULONG(length),0);
   if(result>=0)result=BCryptFinishHash(h,out,32,0);
   if(h)BCryptDestroyHash(h);BCryptCloseAlgorithmProvider(a,0);return result>=0;
 }
 bool sha256(const uint8_t* p,size_t n,uint8_t (&out)[32]){return hash(nullptr,p,n,out);}
 bool hmac_sha256(const uint8_t (&key)[32],const uint8_t* p,size_t n,uint8_t (&out)[32]){return hash(key,p,n,out);}
};
int main(int argc,char** argv){
 assert(argc==3);std::ifstream input(argv[1],std::ios::binary),event(argv[2],std::ios::binary);
 std::vector<uint8_t> receipt((std::istreambuf_iterator<char>(input)),{}),raw((std::istreambuf_iterator<char>(event)),{});
 Crypto crypto;uint8_t key[32],boot[16],digest[32];for(int i=0;i<32;++i)key[i]=i;for(auto& v:boot)v=0x11;
 assert(crypto.sha256(raw.data(),raw.size(),digest));
 rocell_diag::ShoulderReceiptVerifier<Crypto> verifier(crypto,key,boot,"receipt-test");
 assert(verifier.verify({receipt.data(),receipt.size()},0,digest));
 assert(!verifier.verify({receipt.data(),receipt.size()},1,digest));
 for(size_t i=0;i<receipt.size();++i){receipt[i]^=1;assert(!verifier.verify({receipt.data(),receipt.size()},0,digest));receipt[i]^=1;}
 digest[0]^=1;assert(!verifier.verify({receipt.data(),receipt.size()},0,digest));
 // Real SHA/HMAC, host-exported bytes: no fake cryptographic acceptance.
 using Barrier=rocell_diag::CharacterizationExportBarrier<Crypto>;
 Barrier barrier(crypto,key,boot,"receipt-test");
 assert(!barrier.permits_next(1));
 assert(barrier.stage(0,raw.data(),raw.size(),100));
 assert(!barrier.permits_next(1));
 assert(barrier.accept({receipt.data(),receipt.size()},200));
 assert(barrier.permits_next(1)&&!barrier.permits_next(2));
 assert(!barrier.accept({receipt.data(),receipt.size()},300));
 assert(barrier.failed()&&!barrier.permits_next(1));
 Barrier stale(crypto,key,boot,"receipt-test");
 assert(stale.stage(0,raw.data(),raw.size(),100));
 assert(!stale.accept({receipt.data(),receipt.size()},5000101));
 Barrier wrong_campaign(crypto,key,boot,"different-campaign");
 assert(wrong_campaign.stage(0,raw.data(),raw.size(),100));
 assert(!wrong_campaign.accept({receipt.data(),receipt.size()},200));
 Barrier altered(crypto,key,boot,"receipt-test");
 raw[0]^=1;assert(altered.stage(0,raw.data(),raw.size(),100));
 assert(!altered.accept({receipt.data(),receipt.size()},200));raw[0]^=1;
 Barrier reordered(crypto,key,boot,"receipt-test");
 assert(!reordered.stage(1,raw.data(),raw.size(),100));
 assert(!reordered.stage(0,raw.data(),raw.size(),100));
 Barrier overwrite(crypto,key,boot,"receipt-test");
 assert(overwrite.stage(0,raw.data(),raw.size(),100));
 assert(!overwrite.stage(0,raw.data(),raw.size(),200));
 Barrier reversed_clock(crypto,key,boot,"receipt-test");
 assert(reversed_clock.stage(0,raw.data(),raw.size(),100));
 assert(!reversed_clock.accept({receipt.data(),receipt.size()},99));
}

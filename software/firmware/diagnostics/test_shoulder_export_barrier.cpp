#include "shoulder_export_barrier.h"
#include <cassert>
#include <iostream>
#include <string>
// Test doubles exercise control flow only, not cryptographic verification.
struct Digest {bool fail=false;bool sha256(const uint8_t*,size_t n,uint8_t* out){out[0]=uint8_t(n);return !fail;}};
struct Receipt {unsigned sequence;unsigned size;bool verified;};
struct Verifier {int calls=0;bool verify(const Receipt& r,unsigned seq,const uint8_t* hash){++calls;return r.verified&&r.sequence==seq&&r.size==hash[0];}};
int main(){
 using State=rocell_diag::ShoulderExportState;
 {
   Digest digest;Verifier verifier;rocell_diag::ShoulderExportBarrier<Digest,Verifier> gate(digest,verifier);
   assert(gate.stage(0,"record",6,100,1000));assert(gate.state()==State::AwaitingReceipt);
   assert(std::string(gate.retained())=="record");gate.poll(500);assert(gate.state()==State::AwaitingReceipt);
   assert(gate.accept(Receipt{0,6,true},600));assert(gate.state()==State::Released);
   assert(gate.consume());assert(!gate.retained());
   assert(gate.stage(1,"second",6,700,1200));
   assert(!gate.accept(Receipt{0,6,true},800));assert(gate.state()==State::Fault);
   assert(std::string(gate.retained())=="second");
 }
 for(int fault=0;fault<6;++fault){
   Digest digest;Verifier verifier;rocell_diag::ShoulderExportBarrier<Digest,Verifier> gate(digest,verifier);
   assert(gate.stage(0,"record",6,100,1000));
   if(fault==0)assert(!gate.consume());
   if(fault==1)gate.poll(1001);
   if(fault==2)gate.poll(99);
   if(fault==3)assert(!gate.accept(Receipt{0,5,true},500));
   if(fault==4)assert(!gate.accept(Receipt{0,6,false},500));
   if(fault==5)assert(!gate.stage(1,"new",3,200,900));
   assert(gate.state()==State::Fault);assert(!gate.accept(Receipt{0,6,true},600));
   assert(std::string(gate.retained())=="record");
 }
 std::cout<<"SHOULDER_EXPORT_BARRIER_OFFLINE_PASSED\n";
}

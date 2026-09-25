// Offline pause/resume boundary. RAM retention is NOT a durable export.
// ReceiptVerifier must verify a host-persisted, command-bound export receipt;
// this class deliberately provides no unauthenticated acknowledge shortcut.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
namespace rocell_diag {
enum class ShoulderExportState { Empty, AwaitingReceipt, Released, Fault };
template<class Digest,class ReceiptVerifier>
class ShoulderExportBarrier {
 public:
  ShoulderExportBarrier(Digest& digest,ReceiptVerifier& verifier):digest_(digest),verifier_(verifier){}
  bool stage(unsigned sequence,const char* bytes,size_t size,uint64_t now,uint64_t deadline){
    if(state_!=ShoulderExportState::Empty||sequence!=next_||!bytes||!size||size>=sizeof(bytes_)||
       !now||deadline<=now||deadline-now>30000000)return fault();
    if(!digest_.sha256(reinterpret_cast<const uint8_t*>(bytes),size,hash_))return fault();
    memcpy(bytes_,bytes,size);bytes_[size]=0;size_=size;staged_=now;deadline_=deadline;
    state_=ShoulderExportState::AwaitingReceipt;return true;
  }
  template<class Receipt> bool accept(const Receipt& receipt,uint64_t now){
    if(state_!=ShoulderExportState::AwaitingReceipt||now<staged_||now>deadline_)return fault();
    // Verifier owns boot/command binding, receipt authenticity and durable export
    // validation. Sequence and digest identify the exact retained event bytes.
    if(!verifier_.verify(receipt,next_,hash_))return fault();
    state_=ShoulderExportState::Released;return true;
  }
  void poll(uint64_t now){
    if(state_==ShoulderExportState::AwaitingReceipt&&(now<staged_||now>deadline_))fault();
  }
  bool consume(){
    if(state_!=ShoulderExportState::Released)return fault();
    ++next_;size_=0;bytes_[0]=0;state_=ShoulderExportState::Empty;return true;
  }
  const char* retained()const{return size_?bytes_:nullptr;}
  size_t size()const{return size_;}
  ShoulderExportState state()const{return state_;}
 private:
  bool fault(){state_=ShoulderExportState::Fault;return false;}
  Digest& digest_;ReceiptVerifier& verifier_;unsigned next_=0;
  ShoulderExportState state_=ShoulderExportState::Empty;
  uint64_t staged_=0,deadline_=0;size_t size_=0;
  uint8_t hash_[32]={};char bytes_[4096]={};
};
}

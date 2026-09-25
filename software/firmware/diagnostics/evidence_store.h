// Single-owner append-only RAM evidence. No eviction, reset, dynamic allocation,
// network, or disk claim. Keep a native instance off the small control-task stack.
#pragma once
#include <stddef.h>
#include <string.h>

namespace rocell_diag {
template<size_t Slots,size_t Bytes=2048>
class EvidenceStore {
  static_assert(Slots>=4 && Slots<=64,"Bounded evidence slots required");
  static_assert(Bytes>=256 && Bytes<=4096,"Bounded record bytes required");
 public:
  struct Record { char kind[16];char json[Bytes]; };
  EvidenceStore() : count_(0),faulted_(false),records_{} {}
  EvidenceStore(const EvidenceStore&)=delete;
  EvidenceStore& operator=(const EvidenceStore&)=delete;
  bool reserve(size_t records) {
    // Session reserves its entire bounded capture before dispatch. This is an
    // admission check, not a concurrency primitive; one owner must be enforced.
    if(faulted_ || records>Slots-count_) {faulted_=true;return false;}
    return true;
  }
  bool publish(const char* kind,const char* json) {
    if(faulted_ || !kind || !json || count_==Slots) {faulted_=true;return false;}
    size_t k=0,n=0;
    while(k<sizeof(records_[0].kind) && kind[k])++k;
    while(n<Bytes && json[n])++n;
    if(!k || k==sizeof(records_[0].kind) || !n || n==Bytes) {
      faulted_=true;return false;
    }
    memcpy(records_[count_].kind,kind,k+1);
    memcpy(records_[count_].json,json,n+1);
    ++count_;return true;
  }
  const Record* get(size_t index) const {return index<count_?&records_[index]:nullptr;}
  size_t size() const {return count_;}
  bool faulted() const {return faulted_;}
 private:
  size_t count_;
  bool faulted_;
  Record records_[Slots];
};
} // namespace rocell_diag

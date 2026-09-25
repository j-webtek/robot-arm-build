#define HOLD_ADMISSION_NO_MAIN
#include "test_hold_plan_admission.cpp"
#include "held_evidence_digest.h"
int main(int argc,char** argv){
  assert(argc==2);std::ifstream file(argv[1],std::ios::binary);
  static rocell_diag::EvidenceStore<34,4096> store;
  std::string line;
  while(std::getline(file,line)){
    size_t split=line.find('\t');assert(split!=std::string::npos);
    assert(store.publish(line.substr(0,split).c_str(),line.substr(split+1).c_str()));
  }
  Crypto crypto;static rocell_diag::HeldEvidenceDigest digest;
  assert(digest.compute(store,crypto));std::cout<<digest.value()<<"\n";
  return 0;
}

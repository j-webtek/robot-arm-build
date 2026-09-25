#define HOLD_ADMISSION_NO_MAIN
#include "test_hold_plan_admission.cpp"
#include "held_return_admission.h"
int main(int argc,char** argv){
  assert(argc==5);std::ifstream file(argv[1],std::ios::binary);
  std::vector<uint8_t> token((std::istreambuf_iterator<char>(file)),{});
  uint8_t key[32],boot[16],nonce[32];memset(key,'k',32);memset(boot,0x11,16);memset(nonce,0x22,32);
  char session[65],plan[65],evidence[65];
  memset(session,'a',64);session[64]=0;memset(plan,'b',64);plan[64]=0;memset(evidence,'c',64);evidence[64]=0;
  Crypto crypto;rocell_diag::HeldReturnAdmission gate(key,boot,nonce,1000,10001000);
  bool ok=gate.consume(token.data(),token.size(),std::stoull(argv[3]),crypto,
                       session,plan,evidence,2902,argv[4][0]=='1');
  assert(ok==(argv[2][0]=='1'));
  assert(!gate.consume(token.data(),token.size(),1002,crypto,session,plan,evidence,2902,true));
  assert((gate.host_export_hash()!=nullptr)==ok);
  return 0;
}

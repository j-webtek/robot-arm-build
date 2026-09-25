#define HOLD_ADMISSION_NO_MAIN
#include "test_hold_plan_admission.cpp"
#include "held_pair_plan_admission.h"
int main(int argc,char** argv){
  assert(argc==3);std::ifstream file(argv[1],std::ios::binary);
  std::vector<uint8_t> token((std::istreambuf_iterator<char>(file)),{});
  uint8_t key[32],boot[16],nonce[32];memset(key,'k',32);memset(boot,0x11,16);memset(nonce,0x22,32);
  std::string hold(64,'a');Crypto crypto;
  rocell_diag::HeldPairPlanAdmission gate(key,boot,nonce,1000,10001000);
  bool ok=gate.consume(token.data(),token.size(),1001,crypto,policy(),hold.c_str(),"forward","return",6,2);
  assert(ok==(argv[2][0]=='1'));
  assert(!gate.consume(token.data(),token.size(),1001,crypto,policy(),hold.c_str(),"forward","return",6,2));
  if(ok)std::cout<<gate.session_hash()<<"\n";
  else assert(!gate.session_hash()&&!gate.policy_hash());
  return 0;
}

#define NOMINMAX
#define main crypto_cases
#include "test_shoulder_export_receipt.cpp"
#undef main
#include "compensated_shoulder_authorization.h"
#include <string>
#include <iostream>
#include <memory>
int main(int argc,char** argv){
  assert(argc==2);std::string mode=argv[1],lines[3],token;
  for(auto& line:lines)std::getline(std::cin,line);
  std::getline(std::cin,token);std::vector<uint8_t> bytes;
  for(size_t i=0;i<token.size();i+=2)bytes.push_back(uint8_t(std::stoul(token.substr(i,2),nullptr,16)));
  uint8_t key[32],boot[16],nonce[32]={};for(int i=0;i<32;++i)key[i]=i;for(auto& b:boot)b=0x11;
  Crypto crypto;
  auto auth=std::make_unique<rocell_diag::CompensatedShoulderAuthorization>(key,boot,nonce,402000,30402000,"compensated-step-1");
  const char* records[3]={lines[0].c_str(),lines[1].c_str(),lines[2].c_str()};
  size_t sizes[3]={lines[0].size(),lines[1].size(),lines[2].size()};
  uint64_t now=mode=="expired"?30402000:mode=="stale"?2500000:403000;
  bool ok=auth->verify(bytes.data(),bytes.size(),now,crypto,records,sizes);
  bool admitted=auth->contract()!=nullptr;
  assert(admitted==ok);
  assert(!auth->verify(bytes.data(),bytes.size(),now,crypto,records,sizes));
  if(ok){
    auto pose=auth->contract()->reference;pose.started_us=404000;pose.finished_us=405000;
    if(mode=="prewrite_changed")pose.position[1]+=2;
    admitted=auth->contract()->prewrite(pose,406000);
  }
  std::cout<<ok<<" "<<admitted<<"\n";
}

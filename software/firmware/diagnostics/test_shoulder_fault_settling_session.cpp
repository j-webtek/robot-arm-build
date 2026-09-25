#define NOMINMAX
#define main crypto_cases
#include "test_shoulder_export_receipt.cpp"
#undef main
#define main collector_cases
#include "test_shoulder_fault_settling_capture.cpp"
#undef main
#include "shoulder_fault_settling_session.h"
#include <string>
struct Parent {
 std::string raw;
 ShoulderPreloadPhase phase()const{return ShoulderPreloadPhase::Fault;}
 const char* command_id()const{return "receipt-test";}
 const char* boot_id()const{return "11111111111111111111111111111111";}
 const char* record()const{return raw.c_str();}
 size_t record_size()const{return raw.size();}
 unsigned sequence()const{return 0;}
};
std::vector<uint8_t> token(){
 std::string line;std::getline(std::cin,line);std::vector<uint8_t> out;
 if(line.size()!=248)return out;
 for(size_t i=0;i<line.size();i+=2)out.push_back(uint8_t(std::stoul(line.substr(i,2),nullptr,16)));
 return out;
}
int main(){
 Crypto crypto;Parent parent;std::getline(std::cin,parent.raw);
 auto original=parent.raw;uint8_t key[32],boot[16];
 for(int i=0;i<32;++i)key[i]=i;for(auto& b:boot)b=0x11;
 ShoulderFaultSettlingSession<Crypto,Parent> session(crypto,parent,key,boot);
 auto receipt=token();Clock clock;ReadOnlyBus bus;auto admitted=[](){return true;};
 bool ok=session.begin({receipt.data(),receipt.size()},clock.now_us());
 for(int i=0;ok&&i<12;++i){
   clock.tick+=500000;session.advance(bus,clock,admitted);
   if(session.state()!=SettlingState::WaitingExport)break;
   assert(session.record());std::cout<<session.record()<<std::endl;
   receipt=token();ok=session.receipt({receipt.data(),receipt.size()},clock.now_us());
   if(session.state()==SettlingState::Settled)break;
 }
 assert(parent.phase()==ShoulderPreloadPhase::Fault&&parent.raw==original);
 std::cout<<"{\"terminal\":true,\"settled\":"<<(session.state()==SettlingState::Settled?"true":"false")
   <<",\"reads\":"<<bus.reads<<",\"count\":"<<session.count()<<"}"<<std::endl;
}

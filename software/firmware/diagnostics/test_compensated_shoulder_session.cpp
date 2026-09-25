#define NOMINMAX
#define main crypto_cases
#include "test_shoulder_export_receipt.cpp"
#undef main
#include "compensated_shoulder_session.h"
#include "shoulder_fault_settling_session.h"
#include <iostream>
#include <memory>
#include <string>
struct Clock {uint64_t tick=1;uint64_t now_us(){return tick+=100;}};
struct Bus {
 int End=0,Error=0,reads=0,writes=0;std::string mode;
 uint16_t positions[7]={2047,2414,1702,2904,1591,2041,2047};
 uint16_t goals[7]={2047,2405,1709,2907,1589,2040,2047};
 int Read(uint8_t sid,uint8_t address,uint8_t* bytes,uint8_t width){
   ++reads;memset(bytes,0,width);unsigned i=sid-11;
   int value=address==40?1:address==42?goals[i]:address==56?positions[i]:0;
   bytes[0]=value&255;if(width>=2)bytes[1]=value>>8;return width;
 }
 void SyncWritePosEx(uint8_t* ids,uint8_t n,int16_t* targets,uint16_t* speed,uint8_t* acc){
   assert(writes++==0&&n==2&&ids[0]==12&&ids[1]==13);
   assert(speed[0]==20&&speed[1]==20&&acc[0]==1&&acc[1]==1);
   assert(targets[0]==2391&&targets[1]==1723);
   for(int i=0;i<2;++i)goals[i+1]=positions[i+1]=targets[i];
   positions[1]+=10;positions[2]-=7; // Simulated frozen offset, not real hardware.
   if(mode=="short"){positions[1]+=5;positions[2]-=4;}
   if(mode=="neighbor")positions[4]+=4;
   if(mode=="overshoot")positions[1]=2397;
   if(mode=="wrong_goal")goals[1]++;
   if(mode=="at_command")positions[1]=targets[0];
 }
};
std::vector<uint8_t> input(){
 std::string line;std::getline(std::cin,line);std::vector<uint8_t> out;
 if(line=="ABORT"||line.empty())return out;
 for(size_t i=0;i<line.size();i+=2)out.push_back(uint8_t(std::stoul(line.substr(i,2),nullptr,16)));
 return out;
}
int main(int argc,char** argv){
 assert(argc==2);Bus bus;bus.mode=argv[1];Clock clock;Crypto crypto;
 uint8_t key[32],boot[16],nonce[32]={};for(int i=0;i<32;++i)key[i]=i;for(auto& b:boot)b=0x11;
 using Session=rocell_diag::CompensatedShoulderStepSession<Crypto>;
 auto session=std::make_unique<Session>(crypto,key,boot,nonce,1,30000001,"compensated-step-1");
 auto admitted=[](){return true;};using P=rocell_diag::CompensatedStepPhase;
 for(int i=0;i<100;++i){
   clock.tick+=150000;session->advance(bus,clock,admitted);
   if(session->local_phase()==P::Authorization){
     std::cout<<"{\"authorize\":true,\"now_us\":"<<clock.tick<<"}"<<std::endl;
     auto token=input();session->authorize(token.data(),token.size(),clock.now_us());continue;
   }
   if(session->local_phase()==P::Waiting){
     std::cout<<session->record()<<std::endl;auto receipt=input();
     session->receipt({receipt.data(),receipt.size()},clock.now_us());
     if(bus.mode=="prewrite"&&session->local_phase()==P::Write)bus.positions[1]+=2;
   }
   if(session->local_phase()==P::Fault||session->local_phase()==P::Complete)break;
 }
 bool fault=session->local_phase()==P::Fault;
 JsonDocument result;result["terminal"]=true;result["fault"]=fault;result["writes"]=bus.writes;
 result["reason"]=session->reason();
 if(fault&&session->record())result["original"]=session->record();
 serializeJson(result,std::cout);std::cout<<std::endl;
 if(fault&&(bus.mode=="short"||bus.mode=="neighbor"||bus.mode=="overshoot"||bus.mode=="wrong_goal"||bus.mode=="at_command")){
   auto settling=std::make_unique<rocell_diag::ShoulderFaultSettlingSession<Crypto,Session>>(crypto,*session,key,boot);
   auto token=input();assert(settling->begin({token.data(),token.size()},clock.now_us()));
   for(int i=0;i<12;++i){
     clock.tick+=500000;settling->advance(bus,clock,admitted);
     if(settling->state()!=rocell_diag::SettlingState::WaitingExport)break;
     std::cout<<settling->record()<<std::endl;token=input();
     if(!settling->receipt({token.data(),token.size()},clock.now_us()))break;
     if(settling->state()==rocell_diag::SettlingState::Settled)break;
   }
   assert(session->local_phase()==P::Fault&&bus.writes==1);
   std::cout<<"{\"settling_terminal\":true,\"settled\":"<<(settling->state()==rocell_diag::SettlingState::Settled?"true":"false")<<"}"<<std::endl;
 }
}

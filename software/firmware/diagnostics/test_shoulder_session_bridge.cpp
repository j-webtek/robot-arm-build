// Offline process bridge: fake servo bus, real Windows crypto, host receipts.
#define NOMINMAX
#define main crypto_cases
#include "test_shoulder_export_receipt.cpp"
#undef main
#define main preload_cases
#include "test_shoulder_preload_candidate.cpp"
#undef main
#include "shoulder_preload_session.h"
#include "shoulder_session_owner.h"
struct BridgeBus:Bus {
 bool mixed=false,auto_enable=false,preparation=false;
 bool rise=false,recovery=false,stable=false;
 std::string preparation_mode;
 int Read(uint8_t sid,uint8_t address,uint8_t* bytes,uint8_t width){
   if(stable&&!writes&&reads>=28&&sid==14&&address==56&&preparation_mode=="rise_unstable")position[3]=2906;
   if(rise&&writes&&address==56&&(sid==12||sid==13)&&preparation_mode=="rise_slow"){
     int delta=int(goal[sid-11])-int(position[sid-11]);
     position[sid-11]+=delta>4?4:delta<-4?-4:delta;
   }
   return Bus::Read(sid,address,bytes,width);
 }
 void SyncWritePosEx(uint8_t* ids,uint8_t count,int16_t* targets,uint16_t* speeds,uint8_t* acc){
   assert(rise&&writes==0&&count==2&&ids[0]==12&&ids[1]==13);
   if(recovery)assert(targets[0]==2419&&targets[1]==1695);
   else assert(targets[0]==position[1]-12&&targets[1]==position[2]+12);
   for(int i=0;i<2;++i)assert(speeds[i]==20&&acc[i]==1);
   ++writes;goal[1]=targets[0];goal[2]=targets[1];
   if(preparation_mode!="rise_slow"&&preparation_mode!="rise_no_motion"){
     position[1]=targets[0];position[2]=targets[1];
   }
   if(preparation_mode=="rise_wrong_goal")goal[2]=0;
   if(preparation_mode=="rise_plateau"){position[1]=targets[0]+5;position[2]=targets[1]-4;}
   if(preparation_mode=="rise_neighbor")position[4]+=3;
   if(preparation_mode=="rise_wrong_direction")position[1]=recovery?2455:targets[0]+15;
   if(preparation_mode=="rise_read_failure")fail_read=reads;
 }
 int WritePosEx(uint8_t sid,int16_t target,uint16_t speed,uint8_t acc){
   if(preparation){
     assert((sid==11||sid==15||sid==16||sid==17)&&target==position[sid-11]&&speed==20&&acc==1&&writes<4);
     assert(torque[sid-11]==0);++writes;goal[sid-11]=target;if(auto_enable)torque[sid-11]=1;
     if(preparation_mode=="prep_wrong_goal")goal[sid-11]=0;
     if(preparation_mode=="prep_drift")position[4]+=3;
     if(preparation_mode=="prep_neighbor")torque[1]=0;
     if(preparation_mode=="prep_read_failure")fail_read=reads;
     return preparation_mode=="prep_delivery"?0:1;
   }
   if(!mixed)return Bus::WritePosEx(sid,target,speed,acc);
   assert(sid==13&&target==1659&&speed==20&&acc==1&&writes==0);
   ++writes;goal[2]=target;if(auto_enable)torque[2]=1;return 1;
 }
 int broadcasts=0;
 void syncWrite(uint8_t* ids,uint8_t n,uint8_t address,uint8_t* values,uint8_t width){
   assert(ids[0]==12&&ids[1]==13&&n==2&&address==40&&width==1&&values[0]==1&&values[1]==1);
   ++broadcasts;torque[1]=torque[2]=1;
 }
};
int main(int argc,char** argv){
 Crypto crypto;uint8_t key[32],boot[16];for(int i=0;i<32;++i)key[i]=i;for(auto& b:boot)b=0x11;
 BridgeBus bus;Clock clock;auto admitted=[](){return true;};
 const bool mixed=argc>=4;
 const bool preparation=mixed&&std::string(argv[3]).rfind("prep",0)==0;
 const bool stable=mixed&&std::string(argv[3]).rfind("stable",0)==0;
 const bool recovery=stable||(mixed&&std::string(argv[3]).rfind("recover",0)==0);
 const bool rise=recovery||(mixed&&std::string(argv[3]).rfind("rise",0)==0);
 if(mixed){bus.mixed=true;bus.auto_enable=std::string(argv[3])=="enabled";bus.torque[1]=1;bus.goal[1]=2455;}
 if(preparation){
   bus.preparation=true;bus.preparation_mode=argv[3];bus.auto_enable=bus.preparation_mode!="prep_passive";
   for(int i=0;i<7;++i){bus.torque[i]=(i>=1&&i<=3)?1:0;bus.goal[i]=bus.torque[i]?bus.position[i]:0;}
 }
 if(rise){
   bus.rise=true;bus.preparation_mode=argv[3];
   for(int i=0;i<7;++i){bus.torque[i]=1;bus.goal[i]=bus.position[i];}
   if(recovery){
     bus.recovery=true;bus.position[1]=2448;bus.position[2]=1667;bus.position[3]=2905;
     bus.goal[1]=2443;bus.goal[2]=1671;bus.goal[3]=2907;
     bus.stable=stable;if(stable)bus.position[3]=2904;
     const std::string suffix=std::string(argv[3]).substr(stable?6:7);
     bus.preparation_mode="rise"+suffix;
     if(suffix=="_baseline_goal")bus.goal[1]++;
     if(suffix=="_baseline_residual")bus.position[1]+=3;
     if(suffix=="_baseline_elbow_error")bus.position[3]=2904;
   }
   if(bus.preparation_mode=="rise_passive")bus.torque[4]=0;
   if(bus.preparation_mode=="rise_window")bus.position[1]=bus.goal[1]=2048;
 }
 uint8_t nonce[32]={};rocell_diag::ShoulderBusReservation reservation;
 rocell_diag::ShoulderSessionOwner<Crypto> owner(crypto,reservation,key,boot,nonce,0,30000000,
   argc>=3?argv[2]:"receipt-test",stable?rocell_diag::ShoulderSessionScope::StableClearanceRecovery:recovery?rocell_diag::ShoulderSessionScope::ClearanceRecovery:rise?rocell_diag::ShoulderSessionScope::ShoulderRise:preparation?rocell_diag::ShoulderSessionScope::PosePreparation:mixed?rocell_diag::ShoulderSessionScope::MixedTarget:rocell_diag::ShoulderSessionScope::PairHold);
 assert(!owner.session());owner.advance(bus,clock,admitted);assert(bus.writes==0);
 std::vector<uint8_t> start;
 if(argc>=2){
   std::ifstream file(argv[1],std::ios::binary);
   start.assign(std::istreambuf_iterator<char>(file),{});
 }else{
   const char domain[]="rocell.diagnostic-start.v1";
   start.assign(domain,domain+sizeof(domain));start.insert(start.end(),boot,boot+16);
   start.insert(start.end(),nonce,nonce+32);
   for(uint64_t t:{uint64_t(0),uint64_t(30000000)})for(int i=7;i>=0;--i)start.push_back(uint8_t(t>>(i*8)));
   size_t n=strlen(owner.canonical_plan());start.push_back(n>>8);start.push_back(n&255);
   start.insert(start.end(),owner.canonical_plan(),owner.canonical_plan()+n);
   uint8_t digest[32];assert(crypto.hmac_sha256(key,start.data(),start.size(),digest));
   start.insert(start.end(),digest,digest+32);
 }
 if(!owner.start(start.data(),start.size(),clock,admitted)){
   assert(!owner.session()&&bus.writes==0&&bus.broadcasts==0);
   std::cout<<"{\"terminal\":true,\"complete\":false,\"writes\":0,\"broadcasts\":0,\"reason\":\""<<owner.start_reason()<<"\"}"<<std::endl;
   return 0;
 }
 assert(reservation.reserved()&&owner.session());auto& session=*owner.session();
 assert(!owner.start(start.data(),start.size(),clock,admitted));
 using P=rocell_diag::ShoulderPreloadPhase;
 for(int step=0;step<100&&session.phase()!=P::Complete&&session.phase()!=P::Fault;++step){
   clock.tick+=100000;owner.advance(bus,clock,admitted);
   if(session.phase()!=P::Waiting)continue;
   std::cout<<session.record()<<std::endl;
   std::string line;if(!std::getline(std::cin,line))return 2;
   if(line=="ABORT")break; // host export failure: no receipt, no next operation
   // Test-only deterministic transport/export delay advances the controller
   // clock; it is not a firmware command or a wall-clock scheduling claim.
   if(line.rfind("DELAY:",0)==0){
     const auto end=line.find(':',6);if(end==std::string::npos)return 4;
     const auto delay=std::stoull(line.substr(6,end-6));if(delay>11000000)return 5;
     clock.tick+=delay;line=line.substr(end+1);
   }
   if(line.size()!=248)return 3;
   uint8_t token[124];for(int i=0;i<124;++i)token[i]=uint8_t(std::stoul(line.substr(i*2,2),nullptr,16));
   session.receipt(rocell_diag::ShoulderReceiptView{token,sizeof(token)},clock.now_us());
 }
 std::cout<<"{\"terminal\":true,\"complete\":"<<(session.phase()==P::Complete?"true":"false")
   <<",\"writes\":"<<bus.writes<<",\"broadcasts\":"<<bus.broadcasts<<",\"reason\":\""<<session.reason()<<"\"}"<<std::endl;
}

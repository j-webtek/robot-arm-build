#define main preload_cases
#include "test_shoulder_preload_candidate.cpp"
#undef main
#include "shoulder_preload_session.h"
// Explicit noncryptographic test doubles, not deployable receipt verification.
struct Digest {bool sha256(const uint8_t*,size_t,uint8_t* out){out[0]=42;return true;}};
struct Verifier {bool valid=true;bool verify(unsigned receipt,unsigned expected,const uint8_t*){return valid&&receipt==expected;}};
struct PairBus:Bus {
 int broadcasts=0,fault=0;
 void syncWrite(uint8_t* ids,uint8_t n,uint8_t address,uint8_t* values,uint8_t width){
   assert(ids[0]==12&&ids[1]==13&&n==2&&address==40&&width==1&&values[0]==1&&values[1]==1);
   ++broadcasts;torque[1]=1;if(fault!=1)torque[2]=1;
 }
};
int main(){
 using Phase=rocell_diag::ShoulderPreloadPhase;auto admit=[](){return true;};
 // Reproduce the live r23 symptom classes without guessing which occurred:
 // post-write goal mismatch, position drift, torque change or neighbor drift.
 for(int mismatch=0;mismatch<4;++mismatch){
   Digest digest;Verifier verifier;PairBus bus;Clock clock;
   rocell_diag::ShoulderPreloadSession<Digest,Verifier> session(digest,verifier,
     "abababababababababababababababab","failure-evidence",rocell_diag::ShoulderSessionScope::PairHold);
   while(session.phase()!=Phase::Fault){
     session.advance(bus,clock,admit);
     if(session.phase()==Phase::Waiting){
       if(session.sequence()==2){
         if(mismatch==0)bus.goal[1]=0;
         if(mismatch==1)bus.position[1]+=3;
         if(mismatch==2)bus.torque[1]=1;
         if(mismatch==3)bus.position[4]+=3;
       }
       session.receipt(session.sequence(),clock.now_us());
     }
   }
   assert(bus.writes==1&&bus.broadcasts==0&&session.sequence()==3);
   JsonDocument doc;assert(!deserializeJson(doc,session.record()));
   assert(doc["event"]=="STATE_MISMATCH");
   assert(doc["joints"][1][1].as<int>()==bus.position[1]);
   assert(doc["joints"][1][2].as<int>()==bus.goal[1]);
   assert(doc["joints"][1][3].as<int>()==bus.torque[1]);
   assert(doc["joints"][4][1].as<int>()==bus.position[4]);
   const int reads=bus.reads;session.advance(bus,clock,admit);
   assert(bus.reads==reads&&bus.writes==1&&bus.broadcasts==0);
 }
 // A rejected initial pose must be inspectable without any servo mutation.
 for(int enabled=1;enabled<=3;++enabled){
   Digest digest;Verifier verifier;PairBus bus;Clock clock;
   bus.torque[enabled]=1;
   bus.goal[enabled]=0;
   rocell_diag::ShoulderPreloadSession<Digest,Verifier> session(digest,verifier,
       "abababababababababababababababab","baseline-failure");
   session.advance(bus,clock,admit);
   assert(session.phase()==Phase::Fault&&session.sequence()==0);
   assert(bus.writes==0&&bus.broadcasts==0);
   assert(std::string(session.reason())==(enabled<3?"SHOULDERS_NOT_PASSIVE":"ENABLED_JOINT_NOT_TRACKING"));
   JsonDocument doc;assert(!deserializeJson(doc,session.record()));
   assert(doc["event"]=="STATE_MISMATCH");
   assert(doc["joints"][enabled][3].as<int>()==1);
   assert(doc["joints"][enabled][2].as<int>()==0);
   const int reads=bus.reads;session.advance(bus,clock,admit);
   assert(bus.reads==reads&&bus.writes==0&&bus.broadcasts==0);
 }
 for(int fault=0;fault<5;++fault){
   Digest digest;Verifier verifier;Bus bus;Clock clock;
   rocell_diag::ShoulderPreloadSession<Digest,Verifier> session(digest,verifier,"abababababababababababababababab","preload-session");
   for(int step=0;step<20&&session.phase()!=Phase::Complete&&session.phase()!=Phase::Fault;++step){
     session.advance(bus,clock,admit);
     if(session.phase()==Phase::Waiting){
       const int reads=bus.reads,writes=bus.writes;
       assert(session.record()&&session.record_size());
       session.advance(bus,clock,admit);assert(bus.reads==reads&&bus.writes==writes);
       if(session.sequence()==1){
         if(fault==1)bus.position[1]+=3;
         if(fault==2)verifier.valid=false;
         if(fault==3){clock.tick+=11000000;session.advance(bus,clock,admit);continue;}
         if(fault==4)bus.fail_write=1;
       }
       session.receipt(session.sequence(),clock.now_us());
     }
   }
   assert(session.phase()==(fault==0?Phase::Complete:Phase::Fault));
   assert(bus.writes==(fault==0?2:fault==4?1:0));
   if(fault==0){assert(session.sequence()==7);assert(bus.goal[1]==2455&&bus.goal[2]==1659);}
   if(fault==4){assert(session.record());assert(std::string(session.reason())=="DELIVERY_UNCERTAIN");}
   const auto writes=bus.writes;session.advance(bus,clock,admit);assert(bus.writes==writes);
 }
 for(int fault=0;fault<5;++fault){
   Digest digest;Verifier verifier;PairBus bus;bus.fault=fault;Clock clock;
   rocell_diag::ShoulderPreloadSession<Digest,Verifier> session(digest,verifier,
      "abababababababababababababababab","hold-session",rocell_diag::ShoulderSessionScope::PairHold);
   for(int step=0;step<80&&session.phase()!=Phase::Complete&&session.phase()!=Phase::Fault;++step){
     clock.tick+=100000;session.advance(bus,clock,admit);
     if(session.phase()==Phase::Waiting){
       if(session.sequence()==7&&fault==2)bus.position[1]+=3; // after enable intent
       if(session.sequence()==8&&fault==3)clock.tick+=600000; // delayed sent-record receipt
       if(session.sequence()==7&&fault==4)verifier.valid=false;
       session.receipt(session.sequence(),clock.now_us());
     }
   }
   assert(session.phase()==(fault==0?Phase::Complete:Phase::Fault));
   assert(bus.writes==2&&bus.broadcasts==((fault==2||fault==4)?0:1));
   if(fault==0)assert(session.enable_delivery()==rocell_diag::ShoulderEnableDelivery::SentUnacknowledged);
   const int writes=bus.writes,broadcasts=bus.broadcasts;
   session.advance(bus,clock,admit);assert(bus.writes==writes&&bus.broadcasts==broadcasts);
 }
 std::cout<<"SHOULDER_PRELOAD_SESSION_OFFLINE_PASSED\n";
}

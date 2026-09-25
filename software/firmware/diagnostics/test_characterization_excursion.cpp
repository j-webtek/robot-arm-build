#define main existing_owner_fixture
#include "test_shoulder_characterization_owner.cpp"
#undef main

int main(int argc,char** argv){
 assert(argc==2);std::string mode=argv[1];Bus bus;Clock clock;
 rocell_diag::CharacterizationManifest m;m.legs=2;
 for(auto& b:m.bounds){b[0]=0;b[1]=4095;}
 m.goals[0][0]=2397;m.goals[0][1]=1717;
 // First target is valid, but a later target can exceed the original anchor.
 m.goals[1][0]=mode=="outside"?2381:2382;
 m.goals[1][1]=4114-m.goals[1][0];
 auto owner=std::make_unique<rocell_diag::ShoulderCharacterizationOwner>();
 assert(owner->begin(m,clock.now_us()));
 auto evidence=[](const char*,unsigned,const rocell_diag::ShoulderPreloadPose&,
                  const rocell_diag::CharacterizationResult*){return true;};
 auto admitted=[](){return true;};
 for(int i=0;i<5;++i){clock.tick+=200000;owner->advance(bus,clock,evidence,admitted);}
 if(mode=="outside"){
   assert(owner->phase()==rocell_diag::CharacterizationPhase::Fault&&bus.writes==0);
   assert(std::string(owner->reason())=="CAMPAIGN_TARGET_EXCURSION");
 }else{
   assert(bus.writes==1); // Exactly 32-count future target is admitted.
   if(mode=="measured_outside"){
     bus.p[1]=2414-33;clock.tick+=200000;owner->advance(bus,clock,evidence,admitted);
     assert(owner->phase()==rocell_diag::CharacterizationPhase::Fault);
   }
 }
 auto writes=bus.writes;
 if(mode!="boundary")for(int i=0;i<100;++i){clock.tick+=200000;owner->advance(bus,clock,evidence,admitted);}
 assert(bus.writes==writes);
}

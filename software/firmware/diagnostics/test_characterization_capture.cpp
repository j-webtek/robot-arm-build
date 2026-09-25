#define main admission_fixture_main
#include "test_characterization_admission.cpp"
#undef main
#include "characterization_capture.h"
int main(int argc,char** argv){
 assert(argc==2);std::string mode=argv[1];Bus bus;Clock clock;Crypto crypto;
 rocell_diag::CharacterizationCapture capture;unsigned reserves=0;
 auto reserve=[&](){++reserves;return mode!="conflict";};
 auto admitted=[&](){return mode!="lost";};
 bool started=capture.begin(reserve,clock);
 assert(!capture.begin(reserve,clock)&&reserves==1);
 if(started){
   if(mode=="deadline")clock.tick+=1500001;
   if(mode=="clock")clock.tick=0;
   for(int i=0;i<3;++i){if(mode!="clock")clock.tick+=200000;capture.poll(bus,clock,admitted);}
 }
 assert(bus.writes==0);
 if(mode=="success"){
   assert(capture.ready()&&bus.reads==84);
   rocell_diag::CharacterizationPrepare prepare;
   auto owned=[&](){return reserves==1&&capture.ready();};
   auto snapshots=[&](rocell_diag::ShoulderPreloadPose (&p)[3]){return capture.copy(p);};
   unsigned random=0;auto entropy=[&](uint8_t* p,size_t n){memset(p,++random,n);return true;};
   uint16_t bounds[7][2];for(auto& b:bounds){b[0]=0;b[1]=4095;}
   assert(prepare.prepare(owned,snapshots,clock,entropy,crypto,bounds));
   assert(prepare.result()->manifest.legs==12);
 }else assert(capture.failed()&&!capture.ready());
 auto reads=bus.reads;capture.poll(bus,clock,admitted);assert(bus.reads==reads&&!bus.writes);
}

#define main admission_fixture_main
#include "test_characterization_admission.cpp"
#undef main
#include "characterization_controller.h"
struct Services {
 Bus device;Clock timer;std::string mode;unsigned reservations=0,loads=0,random=0;
 bool owned_flag=false;
 bool healthy(){return mode!="health";}
 bool memory_fits(size_t size,size_t reserve){assert(size<32768&&reserve==32768);return mode!="heap";}
 bool reserve(){++reservations;if(mode=="conflict")return false;owned_flag=true;return true;}
 bool owned(){return owned_flag;}
 Clock& clock(){return timer;}Bus& bus(){return device;}
 bool entropy(uint8_t* p,size_t n){memset(p,++random,n);return true;}
 bool load_key(uint8_t (&key)[32]){++loads;for(int i=0;i<32;++i)key[i]=i;return mode!="key";}
 bool boot(uint8_t (&boot)[16]){memset(boot,0x11,16);return true;}
 bool retain(const char*,unsigned,const rocell_diag::ShoulderPreloadPose&,const rocell_diag::CharacterizationResult*){return true;}
 bool release_evidence(unsigned){return true;}
};
int main(int argc,char** argv){
 assert(argc==2);Services services;services.mode=argv[1];Crypto crypto;
 auto controller=std::make_unique<rocell_diag::CharacterizationController<Crypto,Services>>(crypto,services);
 uint16_t bounds[7][2];for(auto& b:bounds){b[0]=0;b[1]=4095;}
 assert(!controller->session()&&!controller->challenge());
 controller->prepare(bounds);assert(!controller->prepare(bounds));
 for(int i=0;i<5;++i){services.timer.tick+=200000;controller->poll();}
 assert(!services.device.writes);
 if(services.mode=="success"){
   assert(controller->session()&&controller->challenge()&&services.device.reads==84&&services.loads==1);
 }else assert(!controller->session()&&!controller->challenge());
 auto reads=services.device.reads;controller->poll();assert(services.device.reads==reads);
}

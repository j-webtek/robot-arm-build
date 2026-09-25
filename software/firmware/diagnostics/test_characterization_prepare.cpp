#define main admission_fixture_main
#include "test_characterization_admission.cpp"
#undef main
#include "characterization_prepare.h"
int main(int argc,char** argv){
 assert(argc==2);std::string mode=argv[1];Crypto crypto;Clock clock;clock.tick=700000;
 rocell_diag::CharacterizationPrepare prepare;unsigned reservations=0,captures=0,random_calls=0;
 auto reserve=[&](){++reservations;return mode!="conflict";};
 auto capture=[&](rocell_diag::ShoulderPreloadPose (&poses)[3]){
   ++captures;if(mode=="capture")return false;
   Bus bus;
   if(mode=="mapping_batch"){
     bus.g[1]=2386;bus.g[2]=1728;bus.p[1]=2391;bus.p[2]=1724;
   }
   if(mode=="separated_mapping_batch"){
     bus.g[1]=2381;bus.g[2]=1733;bus.p[1]=2387;bus.p[2]=1728;
   }
   if(mode=="fine_lookup_validation"){
     bus.g[1]=2387;bus.g[2]=1727;bus.p[1]=2389;bus.p[2]=1726;
   }
   if(mode=="local_interval_campaign"||mode=="ghost_pair_transition_campaign"){
     bus.g[1]=2389;bus.g[2]=1725;bus.p[1]=2391;bus.p[2]=1724;
   }
   if(mode=="visible_interval_campaign"){
     bus.g[1]=2413;bus.g[2]=1701;bus.p[1]=2415;bus.p[2]=1700;
   }
   if(mode=="smoke_direction")bus.p[1]=2396;
   if(mode=="smoke_travel")bus.p[1]=2430;
   for(int n=0;n<3;++n){auto& p=poses[n];p.started_us=100000+n*200000;p.finished_us=p.started_us+10000;
     for(int i=0;i<7;++i){p.position[i]=bus.p[i];p.goal[i]=bus.g[i];p.torque[i]=1;
       p.feedback[i][0]=p.position[i]&255;p.feedback[i][1]=p.position[i]>>8;}}
   if(mode=="moving")poses[2].feedback[1][2]=1;
   if(mode=="raw")poses[2].feedback[1][0]^=1;
   if(mode=="torque")poses[2].torque[1]=0;
   if(mode=="goals")poses[2].goal[1]++;
   if(mode=="stale")clock.tick=2000000;
   if(mode=="order")poses[2].started_us=poses[1].started_us;
   return true;
 };
 auto entropy=[&](uint8_t* bytes,size_t size){++random_calls;memset(bytes,mode=="zero"?0:mode=="same"?1:random_calls,size);return mode!="entropy";};
 uint16_t bounds[7][2];for(auto& b:bounds){b[0]=0;b[1]=4095;}
 if(mode=="bounds"){bounds[1][0]=2410;bounds[1][1]=2420;}
 auto pattern=mode=="matched"?rocell_diag::CharacterizationPattern::Matched:
   mode=="mapping_batch"?rocell_diag::CharacterizationPattern::MappingBatch:
   mode=="separated_mapping_batch"?rocell_diag::CharacterizationPattern::SeparatedMappingBatch:
   mode=="fine_lookup_validation"?rocell_diag::CharacterizationPattern::FineLookupValidation:
   mode=="local_interval_campaign"?rocell_diag::CharacterizationPattern::LocalIntervalCampaign:
   mode=="ghost_pair_transition_campaign"?rocell_diag::CharacterizationPattern::GhostPairTransitionCampaign:
   mode=="visible_interval_campaign"?rocell_diag::CharacterizationPattern::VisibleIntervalCampaign:
   mode.rfind("smoke",0)==0?rocell_diag::CharacterizationPattern::Smoke:
   mode=="invalid_pattern"?static_cast<rocell_diag::CharacterizationPattern>(99):rocell_diag::CharacterizationPattern::Legacy;
 bool ok=prepare.prepare(reserve,capture,clock,entropy,crypto,bounds,pattern);
 assert(ok==(mode=="success"||mode=="matched"||mode=="smoke"||mode=="mapping_batch"||mode=="separated_mapping_batch"||mode=="fine_lookup_validation"||mode=="local_interval_campaign"||mode=="ghost_pair_transition_campaign"||mode=="visible_interval_campaign"));assert((prepare.result()!=nullptr)==ok);
 if(ok){auto& p=*prepare.result();
   assert(p.manifest.goals[0][0]==(mode=="visible_interval_campaign"?2401:mode=="separated_mapping_batch"?2389:(mode=="mapping_batch"||mode=="fine_lookup_validation"||mode=="local_interval_campaign"||mode=="ghost_pair_transition_campaign")?2377:2397));
   assert(p.manifest.goals[0][1]==(mode=="visible_interval_campaign"?1713:mode=="separated_mapping_batch"?1725:(mode=="mapping_batch"||mode=="fine_lookup_validation"||mode=="local_interval_campaign"||mode=="ghost_pair_transition_campaign")?1737:1717));
   assert(p.manifest.legs==(mode=="smoke"?1:mode=="visible_interval_campaign"?4:mode=="local_interval_campaign"?11:12)&&p.expires_us-p.issued_us==30000000);
   for(unsigned i=0;i<p.manifest.legs;++i)printf("%u %u\n",p.manifest.goals[i][0],p.manifest.goals[i][1]);}
 auto before=captures;assert(!prepare.prepare(reserve,capture,clock,entropy,crypto,bounds));
 assert(reservations==(mode=="invalid_pattern"?0u:1u)&&captures==before);
}

// Offline composition owner. Services must bind actual board reservation,
// health, heap checks, existing key loading, boot identity and hardware entropy.
// Call from the same task as route dispatch. Never allocate on the task stack.
#pragma once
#include "characterization_capture.h"
#include "characterization_challenge.h"
#include <memory>
#include <new>
#include <cstdio>
namespace rocell_diag {
template<class Crypto,class Services> class CharacterizationController {
 public:
  using Session=CharacterizationSession<Crypto>;
  CharacterizationController(Crypto& crypto,Services& services,
      CharacterizationPattern pattern=CharacterizationPattern::Legacy)
      :crypto_(crypto),services_(services),pattern_(pattern){}
  bool prepare(const uint16_t (&reviewed_bounds)[7][2]){
    if(attempted_)return false;attempted_=true;
    if(pattern_!=CharacterizationPattern::Legacy&&pattern_!=CharacterizationPattern::Matched&&pattern_!=CharacterizationPattern::Smoke&&pattern_!=CharacterizationPattern::Matrix&&pattern_!=CharacterizationPattern::Repeatability&&pattern_!=CharacterizationPattern::ABControl&&pattern_!=CharacterizationPattern::ABCandidate&&pattern_!=CharacterizationPattern::ForwardRepeat&&pattern_!=CharacterizationPattern::ReverseCandidate&&pattern_!=CharacterizationPattern::ReverseControl&&pattern_!=CharacterizationPattern::HeldoutCandidate&&pattern_!=CharacterizationPattern::HeldoutControl&&pattern_!=CharacterizationPattern::SecondHeldoutCandidate&&pattern_!=CharacterizationPattern::SecondHeldoutControl&&pattern_!=CharacterizationPattern::MappingBatch&&pattern_!=CharacterizationPattern::SeparatedMappingBatch&&pattern_!=CharacterizationPattern::FineLookupValidation&&pattern_!=CharacterizationPattern::LocalIntervalCampaign&&pattern_!=CharacterizationPattern::GhostPairTransitionCampaign&&pattern_!=CharacterizationPattern::VisibleIntervalCampaign)return fail("PATTERN_INVALID");
    if(!services_.healthy()||!services_.memory_fits(sizeof(Session),32768))return fail("PREPARE_PREFLIGHT");
    memcpy(bounds_,reviewed_bounds,sizeof(bounds_));
    auto reserve=[&](){return services_.reserve();};
    if(!capture_.begin(reserve,services_.clock()))return fail("RESERVATION_FAILED");
    state_=State::Capturing;return true;
  }
  void poll(){
    auto admitted=[&](){return services_.healthy()&&services_.owned();};
    if(state_==State::Capturing){
      capture_.poll(services_.bus(),services_.clock(),admitted);
      if(capture_.failed()){fail("CAPTURE_FAILED");return;}
      if(!capture_.ready())return;
      auto owned=[&](){return admitted();};
      auto snapshots=[&](ShoulderPreloadPose (&p)[3]){return capture_.copy(p);};
      auto entropy=[&](uint8_t* bytes,size_t size){return services_.entropy(bytes,size);};
      if(!preparation_.prepare(owned,snapshots,services_.clock(),entropy,crypto_,bounds_,pattern_)){
        fail("PREPARATION_FAILED");return;
      }
      uint8_t key[32]={},boot[16]={};
      if(!services_.load_key(key)||!services_.boot(boot)||!services_.memory_fits(sizeof(Session),32768)){
        wipe(key);fail("SESSION_PREFLIGHT");return;
      }
      uint8_t any=0;for(auto byte:key)any|=byte;
      if(!any){wipe(key);fail("KEY_INVALID");return;}
      const auto& p=*preparation_.result();
      session_.reset(new(std::nothrow) Session(crypto_,key,boot,p.nonce,p.issued_us,p.expires_us,p.campaign,p.reference,p.manifest));
      wipe(key);
      if(!session_){fail("SESSION_ALLOCATION");return;}
      memcpy(boot_,boot,sizeof(boot_));
      if(!services_.memory_fits(0,32768)){session_.reset();fail("SESSION_HEADROOM");return;}
      state_=State::Ready;return;
    }
    if(state_==State::Ready&&session_){
      if(session_->completed()!=released_){
        if(session_->completed()!=released_+1||!services_.release_evidence(session_->completed())){
          fail("EVIDENCE_RELEASE_FAILED");return;
        }
        released_=session_->completed();
      }
      auto evidence=[&](const char* event,unsigned leg,const ShoulderPreloadPose& pose,const CharacterizationResult* result){
        return services_.retain(event,leg,pose,result);
      };
      session_->advance(services_.bus(),services_.clock(),evidence,admitted);
    }
  }
  // Caller still must authenticate requests before using this access point.
  Session* session(){return state_==State::Ready?session_.get():nullptr;}
  const PreparedCharacterization* challenge()const{return state_==State::Ready?preparation_.result():nullptr;}
  const char* reason()const{return reason_;}
  size_t publish_reference(uint8_t* output,size_t capacity)const{
    return state_==State::Ready?preparation_.copy_reference(output,capacity):0;
  }
  // Owner-task-only snapshot: no bus acquisition or lifecycle advancement.
  // A future network adapter must authenticate and freshness-bind these bytes.
  size_t recovery_snapshot(char* output,size_t capacity){
    if(!output||!capacity||!session())return 0;
    auto hex=[](const uint8_t* bytes,size_t size,char* out){
      const char* digits="0123456789abcdef";
      for(size_t i=0;i<size;++i){out[2*i]=digits[bytes[i]>>4];out[2*i+1]=digits[bytes[i]&15];}
      out[2*size]=0;
    };
    uint8_t receipt[32],record[32];unsigned leg;size_t size;
    bool accepted=session_->last_receipt(receipt);
    bool retained=session_->recovery_record(leg,size,record);
    char boot[33],receipt_hex[65],record_hex[65],leg_text[12];
    hex(boot_,16,boot);hex(receipt,32,receipt_hex);hex(record,32,record_hex);
    if(retained)snprintf(leg_text,sizeof(leg_text),"%u",leg);else strcpy(leg_text,"null");
    int n=snprintf(output,capacity,
      "{\"boot\":\"%s\",\"campaign\":\"%s\",\"completed\":%u,\"phase\":\"%s\","
      "\"last_receipt_sha256\":%s%s%s,\"retained_leg\":%s,\"retained_size\":%u,"
      "\"retained_sha256\":%s%s%s}",boot,session_->campaign_id(),session_->completed(),state_name(),
      accepted?"\"":"",accepted?receipt_hex:"null",accepted?"\"":"",leg_text,unsigned(size),
      retained?"\"":"",retained?record_hex:"null",retained?"\"":"");
    return n>0&&size_t(n)<capacity?size_t(n):0;
  }
  size_t publish_challenge(uint8_t* output,size_t capacity)const{
    if(state_!=State::Ready||session_->phase()!=CharacterizationPhase::New)return 0;
    return encode_characterization_challenge(*preparation_.result(),boot_,output,capacity);
  }
  const char* state_name()const{
    if(state_==State::New)return "NEW";
    if(state_==State::Capturing)return "CAPTURING";
    if(state_==State::Failed)return "FAULT";
    switch(session_->phase()){
      case CharacterizationPhase::New:return "AWAITING_AUTHORIZATION";
      case CharacterizationPhase::Baseline:return "BASELINE";
      case CharacterizationPhase::Prewrite:return "PREWRITE";
      case CharacterizationPhase::Observe:return "OBSERVE";
      case CharacterizationPhase::AwaitExport:return "AWAITING_EXPORT";
      case CharacterizationPhase::Complete:return "COMPLETE";
      case CharacterizationPhase::Fault:return "FAULT";
    }
    return "FAULT";
  }
 private:
  enum class State{New,Capturing,Ready,Failed};
  bool fail(const char* reason){state_=State::Failed;reason_=reason;return false;}
  static void wipe(uint8_t (&key)[32]){volatile uint8_t* p=key;for(unsigned i=0;i<32;++i)p[i]=0;}
  Crypto& crypto_;Services& services_;State state_=State::New;bool attempted_=false;
  const CharacterizationPattern pattern_;
  const char* reason_="NONE";uint16_t bounds_[7][2]={};
  unsigned released_=0;
  uint8_t boot_[16]={};
  CharacterizationCapture capture_;CharacterizationPrepare preparation_;std::unique_ptr<Session> session_;
};
}

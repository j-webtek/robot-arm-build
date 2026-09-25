// Pair-only HTTP composition. The firmware supplies a reviewed one-use prepare
// callback; registration never reads files, initializes hardware or moves.
// Allocate this object off the ESP32 loop stack and keep it alive with the server.
#pragma once
#include <cstddef>
#include <cstdio>
namespace rocell_diag {
template<class Pair,class Prepare,class WebServer>
class ConfiguredHeldPairRoutes {
 public:
  ConfiguredHeldPairRoutes(Pair& pair,Prepare& prepare,WebServer& server)
      :pair_(pair),prepare_(prepare),server_(server){}
  ConfiguredHeldPairRoutes(const ConfiguredHeldPairRoutes&)=delete;
  ConfiguredHeldPairRoutes& operator=(const ConfiguredHeldPairRoutes&)=delete;
  void register_routes(){
    if(registered_)return;registered_=true;
    server_.on("/rocell/held-pair/prepare",HTTP_POST,[this](){
      no_cache();
      if(prepare_attempted_){error(409,"PAIR_PREPARE_CONSUMED");return;}
      prepare_attempted_=true;
      // This retires hold evidence; host must have exported it before requesting.
      if(!prepare_()){error(503,"PAIR_PREPARATION_FAILED");return;}
      ready_=true;
      if(!pair_.issue_initial(challenge_,sizeof(challenge_))){
        error(503,"PAIR_INITIAL_CHALLENGE_FAILED");return;}
      server_.send(200,"application/json",challenge_);
    });
    server_.on("/rocell/held-pair/return-challenge",HTTP_POST,[this](){
      no_cache();if(!available())return;
      if(return_attempted_){error(409,"PAIR_RETURN_CHALLENGE_CONSUMED");return;}
      return_attempted_=true;
      if(!pair_.issue_return(challenge_,sizeof(challenge_))){
        error(409,"PAIR_RETURN_NOT_AVAILABLE");return;}
      server_.send(200,"application/json",challenge_);
    });
    server_.on("/rocell/held-pair/status",HTTP_GET,[this](){
      no_cache();if(!available())return;
      if(!pair_.status_json(response_,1024)){serialization_failed();return;}
      server_.send(200,"application/json",response_);
    });
    server_.on("/rocell/held-pair/record",HTTP_GET,[this](){
      no_cache();if(!available())return;
      const auto query=server_.arg("index");
      if(query.length()==0||query.length()>2||(query.length()>1&&query[0]=='0')){
        error(400,"INVALID_INDEX");return;}
      size_t index=0;
      for(size_t i=0;i<query.length();++i){
        if(query[i]<'0'||query[i]>'9'){error(400,"INVALID_INDEX");return;}
        index=index*10+size_t(query[i]-'0');
      }
      if(index>=34||index>=pair_.record_count()){error(404,"RECORD_NOT_FOUND");return;}
      if(!pair_.record_json(index,response_,sizeof(response_))){serialization_failed();return;}
      server_.send(200,"application/json",response_);
    });
  }
 private:
  bool available(){
    if(!ready_){error(503,"PAIR_NOT_PREPARED");return false;}
    if(pair_.exclusive_work()){error(409,"PAIR_ACTIVE");return false;}
    return true;
  }
  void no_cache(){server_.sendHeader("Cache-Control","no-store");}
  void error(int code,const char* reason){
    // All reasons above are fixed ASCII constants, never caller-provided text.
    snprintf(response_,sizeof(response_),"{\"error\":\"%s\"}",reason);
    server_.send(code,"application/json",response_);
  }
  void serialization_failed(){pair_.export_failed();error(500,"PAIR_SERIALIZATION_FAILED");}
  Pair& pair_;Prepare& prepare_;WebServer& server_;
  bool registered_=false,prepare_attempted_=false,return_attempted_=false,ready_=false;
  char challenge_[512]={},response_[9216]={};
};

// Use as the exclusive diagnostic loop, not alongside legacy command handling.
// Either active acquisition keeps synchronous WebServer work off the bus owner.
template<class Hold,class Pair,class WebServer>
void poll_hold_pair_diagnostics(Hold& hold,Pair& pair,WebServer& web){
  hold.poll();pair.poll();
  if(!hold.exclusive_work()&&!pair.exclusive_work())web.handleClient();
}
template<class Hold,class Pair,class Recovery,class WebServer>
void poll_hold_pair_recovery_diagnostics(Hold& hold,Pair& pair,Recovery& recovery,WebServer& web){
  hold.poll();pair.poll();recovery.poll();
  if(!hold.exclusive_work()&&!pair.exclusive_work()&&!recovery.exclusive_work())web.handleClient();
}
}

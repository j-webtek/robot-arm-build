// Explicit recovery HTTP surface. Registration/readout never prepares or moves.
// Prepare must atomically exclude ordinary hold/pair admission, load the reviewed
// policy/key, initialize the recovery listener, and serialize its finite challenge.
// Preparation failure consumes this route; no retry, reset, or implicit recovery.
#pragma once
#include <cstddef>
#include <cstdio>
namespace rocell_diag {
template<class Recovery,class Prepare,class WebServer>
class ConfiguredRecoveryRoutes {
 public:
  ConfiguredRecoveryRoutes(Recovery& runtime,Prepare& prepare,WebServer& server)
      :runtime_(runtime),prepare_(prepare),server_(server){}
  void register_routes(){
    if(registered_)return;registered_=true;
    server_.on("/rocell/recovery/prepare",HTTP_POST,[this](){
      no_cache();
      if(server_.args()!=0){error(400,"RECOVERY_PARAMETERS_FORBIDDEN");return;}
      if(attempted_){error(409,"RECOVERY_PREPARE_CONSUMED");return;}
      attempted_=true;
      if(!prepare_(challenge_,sizeof(challenge_))){
        runtime_.interference();error(503,"RECOVERY_PREPARATION_FAILED");return;
      }
      ready_=true;server_.send(200,"application/json",challenge_);
    });
    server_.on("/rocell/recovery/status",HTTP_GET,[this](){
      no_cache();
      if(server_.args()!=0){error(400,"RECOVERY_PARAMETERS_FORBIDDEN");return;}
      if(!available())return;
      if(!runtime_.status_json(response_,512)){serialization_failed();return;}
      server_.send(200,"application/json",response_);
    });
    server_.on("/rocell/recovery/record",HTTP_GET,[this](){
      no_cache();
      if(server_.args()!=1){error(400,"INVALID_INDEX");return;}
      if(!available())return;
      const auto query=server_.arg("index");
      if(query.length()==0||query.length()>2||(query.length()>1&&query[0]=='0')){
        error(400,"INVALID_INDEX");return;
      }
      size_t index=0;
      for(size_t i=0;i<query.length();++i){
        if(query[i]<'0'||query[i]>'9'){error(400,"INVALID_INDEX");return;}
        index=index*10+size_t(query[i]-'0');
      }
      if(index>=12||index>=runtime_.size()){error(404,"RECORD_NOT_FOUND");return;}
      if(!runtime_.record_json(index,response_,sizeof(response_))){serialization_failed();return;}
      server_.send(200,"application/json",response_);
    });
  }
 private:
  bool available(){
    if(!ready_){error(503,"RECOVERY_NOT_PREPARED");return false;}
    if(runtime_.exclusive_work()){error(409,"RECOVERY_ACTIVE");return false;}
    return true;
  }
  void no_cache(){server_.sendHeader("Cache-Control","no-store");}
  void error(int code,const char* reason){
    snprintf(response_,sizeof(response_),"{\"error\":\"%s\"}",reason);
    server_.send(code,"application/json",response_);
  }
  void serialization_failed(){runtime_.export_failed();error(500,"RECOVERY_SERIALIZATION_FAILED");}
  Recovery& runtime_;Prepare& prepare_;WebServer& server_;
  bool registered_=false,attempted_=false,ready_=false;
  char challenge_[512]={},response_[4608]={};
};
}
